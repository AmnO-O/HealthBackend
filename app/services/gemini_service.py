import json
import logging
from google import genai
from google.genai import types
from typing import List, Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger("vitalis-gemini")

# JSON schema that Gemini must follow for chat responses
CHAT_RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "message": types.Schema(
            type=types.Type.STRING,
            description="The main response text. Use markdown formatting (bold with **, bullet points with •, newlines)."
        ),
        "suggested_actions": types.Schema(
            type=types.Type.ARRAY,
            description="0-3 contextual action buttons to display below the message. Only include when genuinely useful.",
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "label": types.Schema(
                        type=types.Type.STRING,
                        description="Short button label, e.g. 'Save to Diary', 'View Recipe', 'Log Water'"
                    ),
                    "type": types.Schema(
                        type=types.Type.STRING,
                        description="One of: SAVE_TO_DIARY, VIEW_RECIPE, LOG_WATER, SHOW_EXERCISES, ASK_FOLLOWUP, CUSTOM",
                        enum=["SAVE_TO_DIARY", "VIEW_RECIPE", "LOG_WATER", "SHOW_EXERCISES", "ASK_FOLLOWUP", "CUSTOM"]
                    ),
                    "icon": types.Schema(
                        type=types.Type.STRING,
                        description="Icon identifier: bookmark, menu_book, water_drop, fitness_center, chat, check",
                        enum=["bookmark", "menu_book", "water_drop", "fitness_center", "chat", "check"]
                    ),
                },
                required=["label", "type", "icon"]
            )
        ),
        "quick_replies": types.Schema(
            type=types.Type.ARRAY,
            description="2-4 short follow-up questions the user might want to ask next. Keep them concise (under 40 chars).",
            items=types.Schema(type=types.Type.STRING)
        ),
    },
    required=["message", "suggested_actions", "quick_replies"]
)


class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL_NAME
        self.client = None

        # Plain text config for non-chat endpoints (e.g. analyze_places)
        self.config = types.GenerateContentConfig(
            system_instruction="You are Vitalis AI, a specialized health and wellness assistant. "
                               "Your goal is to provide helpful, evidence-based wellness advice, "
                               "analyze health locations, and encourage a healthy lifestyle. "
                               "Always maintain a professional, supportive, and informative tone. "
                               "If asked for medical diagnosis, advise seeing a professional while "
                               "providing general wellness context."
        )

        # Structured JSON config for chat with action chips
        self.chat_config = types.GenerateContentConfig(
            system_instruction=(
                "You are Vitalis AI, a specialized health and wellness assistant. "
                "Your goal is to provide helpful, evidence-based wellness advice, "
                "dietary suggestions, hydration tracking, exercise recommendations, "
                "and sleep optimization tips. "
                "Always maintain a professional, supportive, and informative tone. "
                "If asked for medical diagnosis, advise seeing a professional while "
                "providing general wellness context.\n\n"
                "RESPONSE GUIDELINES:\n"
                "- 'message': Your main reply. Use markdown: **bold** for emphasis, bullet points (• or -), newlines for structure.\n"
                "- 'suggested_actions': 0-3 contextual action buttons. Use these types:\n"
                "  * SAVE_TO_DIARY + bookmark icon: when you give a recommendation worth saving\n"
                "  * VIEW_RECIPE + menu_book icon: when you suggest food/meals with recipes\n"
                "  * LOG_WATER + water_drop icon: when discussing hydration and user should log water\n"
                "  * SHOW_EXERCISES + fitness_center icon: when suggesting exercises\n"
                "  * ASK_FOLLOWUP + chat icon: for deeper conversation prompts\n"
                "  * CUSTOM + check icon: for other actions\n"
                "- 'quick_replies': 2-4 short follow-up questions (under 40 chars each) the user might ask next.\n"
                "  Make them contextually relevant to your response.\n\n"
                "Keep responses concise and actionable. Respond in the same language as the user's message."
            ),
            response_mime_type="application/json",
            response_schema=CHAT_RESPONSE_SCHEMA,
        )

        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"Gemini Service initialized with model: {self.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Service: {e}")
        else:
            logger.warning("GEMINI_API_KEY not found in settings. AI features will be disabled.")

    def _map_history(self, history: List[Dict[str, str]]) -> List[types.Content]:
        """Maps incoming history dictionaries to SDK Content objects."""
        if not history:
            return []

        mapped_history = []
        for entry in history:
            role = "user" if entry.get("role") == "user" else "model"
            content = types.Content(
                role=role,
                parts=[types.Part(text=entry.get("content", ""))]
            )
            mapped_history.append(content)
        return mapped_history

    def _parse_structured_response(self, raw_text: str) -> Dict[str, Any]:
        """Parse the structured JSON response from Gemini.
        
        Falls back to plain text with empty actions/quick_replies if parsing fails.
        """
        try:
            parsed = json.loads(raw_text)
            return {
                "message": parsed.get("message", raw_text),
                "suggested_actions": parsed.get("suggested_actions", []),
                "quick_replies": parsed.get("quick_replies", []),
            }
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse structured response, falling back to plain text: {e}")
            return {
                "message": raw_text,
                "suggested_actions": [],
                "quick_replies": [],
            }

    async def get_chat_response(self, message: str, history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """Health and wellness chat response with structured actions.
        
        Returns a dict with 'message', 'suggested_actions', and 'quick_replies'.
        """
        if not self.client:
            return {
                "message": "AI service is currently unavailable. Please check API configuration.",
                "suggested_actions": [],
                "quick_replies": [],
            }

        logger.info(f"Chat Request - Message: {message[:100]}...")
        try:
            # Map history to types.Content
            sdk_history = self._map_history(history or [])

            # Start a chat session with the provided history and structured config
            chat = self.client.aio.chats.create(
                model=self.model_name,
                history=sdk_history,
                config=self.chat_config
            )

            # Send the message within the session
            response = await chat.send_message(message)
            raw_text = response.text
            logger.info(f"Chat Response (raw): {raw_text[:200]}...")

            # Parse the structured JSON response
            result = self._parse_structured_response(raw_text)
            logger.info(f"Parsed response - Actions: {len(result['suggested_actions'])}, Quick replies: {len(result['quick_replies'])}")
            return result
        except Exception as e:
            logger.error(f"Error in Gemini chat: {e}")
            return {
                "message": f"I'm sorry, I encountered an error while processing your request: {str(e)}",
                "suggested_actions": [],
                "quick_replies": [],
            }

    async def analyze_places(self, user_context: str, places: List[Dict[str, Any]]) -> str:
        """Analyzes a list of places based on user's health context (single-turn)."""
        if not self.client:
            return "AI analysis is currently unavailable."

        logger.info(f"Analysis Request - Context: {user_context[:100]}..., Places Count: {len(places)}")
        places_str = "\n".join([
            f"- {p['name']} ({p['category']}): {p.get('subtitle') or p['address']}"
            for p in places
        ])

        prompt = (
            f"User context: {user_context}\n\n"
            f"Here are some nearby wellness spots:\n{places_str}\n\n"
            "Please analyze these spots and suggest which ones are most beneficial "
            "for the user's specific context. Provide brief, actionable insights for each recommended spot."
        )

        try:
            # Use generate_content for single-turn analysis (plain text, no structured output)
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=self.config
            )
            logger.info(f"Analysis Response - Text: {response.text[:100]}...")
            return response.text
        except Exception as e:
            logger.error(f"Error in Gemini place analysis: {e}")
            return "Failed to analyze places. Please try again later."

# Singleton instance
gemini_service = GeminiService()
