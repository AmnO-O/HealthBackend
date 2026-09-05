import json
import logging
from google import genai
from google.genai import types, errors
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
        self.api_keys = settings.gemini_api_keys
        self.model_name = settings.GEMINI_MODEL_NAME
        self._current_key_index = 0
        self._clients = {}  # Cache clients by key

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

        if not self.api_keys:
            logger.warning("No GEMINI_API_KEY found in settings. AI features will be disabled.")

    def _get_client(self) -> Optional[genai.Client]:
        """Lazily initializes and returns the client for the current API key."""
        if not self.api_keys:
            return None

        current_key = self.api_keys[self._current_key_index]
        if current_key not in self._clients:
            try:
                self._clients[current_key] = genai.Client(api_key=current_key)
                logger.info(f"Initialized Gemini client for key at index {self._current_key_index}")
            except Exception as e:
                logger.error(f"Failed to initialize client for key at index {self._current_key_index}: {e}")
                return None
        return self._clients[current_key]

    def _rotate_key(self) -> bool:
        """Rotates to the next available API key. Returns True if rotated, False if only one key exists."""
        if len(self.api_keys) <= 1:
            return False

        old_index = self._current_key_index
        self._current_key_index = (self._current_key_index + 1) % len(self.api_keys)
        logger.warning(f"Rotating Gemini API key from index {old_index} to {self._current_key_index}")
        return True

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

    async def get_chat_response(
        self,
        message: str,
        history: List[Dict[str, str]] = None,
        image_base64: Optional[str] = None
    ) -> Dict[str, Any]:
        """Health and wellness chat response with optional image support and API rotation."""

        # Determine number of attempts (max one per key)
        num_attempts = len(self.api_keys) if self.api_keys else 1

        last_error = "No API keys configured."

        for attempt in range(num_attempts):
            client = self._get_client()
            if not client:
                last_error = "Failed to initialize AI client."
                if self._rotate_key(): continue
                break

            logger.info(f"Chat Request (Attempt {attempt+1}/{num_attempts}) - Has Image: {image_base64 is not None}")
            try:
                sdk_history = self._map_history(history or [])
                message_parts = [types.Part(text=message)]

                if image_base64:
                    b64_data = image_base64
                    mime_type = "image/jpeg"
                    if "," in b64_data:
                        header, b64_data = b64_data.split(",", 1)
                        if "image/png" in header: mime_type = "image/png"
                        elif "image/webp" in header: mime_type = "image/webp"

                    message_parts.append(
                        types.Part(
                            inline_data=types.Blob(
                                data=b64_data,
                                mime_type=mime_type
                            )
                        )
                    )

                chat = client.aio.chats.create(
                    model=self.model_name,
                    history=sdk_history,
                    config=self.chat_config
                )

                response = await chat.send_message(message_parts)

                # Guard against blocked or empty responses
                raw_text = getattr(response, "text", None)
                if not raw_text:
                    finish_reason = "UNKNOWN"
                    try:
                        finish_reason = response.candidates[0].finish_reason
                    except (AttributeError, IndexError):
                        pass

                    error_msg = {
                        "SAFETY": "I'm sorry, but I can't fulfill this request as it was flagged by safety filters.",
                        "RECITATION": "The response was blocked due to recitation policy.",
                        "OTHER": "The AI was unable to generate a response for this query.",
                    }.get(finish_reason, "The AI returned an empty response. Please try rephrasing.")

                    return {
                        "message": error_msg,
                        "suggested_actions": [],
                        "quick_replies": ["Can you try a different question?"],
                    }

                return self._parse_structured_response(raw_text)

            except Exception as e:
                status_code = getattr(e, 'code', None)
                # 429 = Too Many Requests (Quota), 500/503 = Server errors
                if status_code in [429, 500, 503] or "quota" in str(e).lower():
                    last_error = str(e)
                    rotated = self._rotate_key()
                    if attempt < num_attempts - 1 and rotated:
                        logger.warning(f"Retryable error {status_code} on key index {(self._current_key_index - 1) % num_attempts}. Rotating...")
                        continue
                    else:
                        logger.error(f"Quota exhausted on all keys tried.")

                # Non-retryable error (400, 401, 403, etc.)
                logger.error(f"Permanent error on key at index {self._current_key_index}: {e}")
                last_error = str(e)
                break

        return {
            "message": f"I'm sorry, I encountered an error while processing your request: {last_error}",
            "suggested_actions": [],
            "quick_replies": [],
        }

    async def analyze_places(self, user_context: str, places: List[Any]) -> str:
        """Analyzes a list of places with API rotation support."""
        num_attempts = len(self.api_keys) if self.api_keys else 1
        last_error = "AI analysis is currently unavailable."

        # Construction using Pydantic model attributes
        places_str = "\n".join([
            f"- {p.name} ({p.category}): {p.subtitle or p.address}"
            for p in places
        ])

        prompt = (
            f"User context: {user_context}\n\n"
            f"Here are some nearby wellness spots:\n{places_str}\n\n"
            "Please analyze these spots and suggest which ones are most beneficial "
            "for the user's specific context. Provide brief, actionable insights for each recommended spot."
        )

        for attempt in range(num_attempts):
            client = self._get_client()
            if not client:
                if self._rotate_key(): continue
                break

            try:
                response = await client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=self.config
                )

                raw_text = getattr(response, "text", None)
                if not raw_text:
                    return "The AI was unable to analyze these locations at this time."

                return raw_text
            except Exception as e:
                status_code = getattr(e, 'code', None)
                if status_code in [429, 500, 503] or "quota" in str(e).lower():
                    last_error = str(e)
                    rotated = self._rotate_key()
                    if attempt < num_attempts - 1 and rotated:
                        logger.warning(f"Retryable error {status_code} in analyze_places on key index {(self._current_key_index - 1) % num_attempts}")
                        continue
                logger.error(f"Permanent error in analyze_places on key index {self._current_key_index}: {e}")
                last_error = str(e)
                break

        return f"Failed to analyze places: {last_error}"

# Singleton instance
gemini_service = GeminiService()
