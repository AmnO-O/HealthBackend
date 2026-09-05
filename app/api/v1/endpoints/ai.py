import logging
from fastapi import APIRouter
from app.models.schemas import AIChatRequest, AIAnalyzePlacesRequest, AIResponse, SuggestedAction
from app.services.gemini_service import gemini_service

router = APIRouter()
logger = logging.getLogger("vitalis-ai")

@router.get("/ping")
async def ai_ping():
    """Lightweight health ping to wake up the service."""
    return {"status": "awake"}

@router.post("/chat", response_model=AIResponse)
async def ai_chat(request: AIChatRequest):
    """Health-focused AI chat powered by Gemini with structured action chips and image support."""
    logger.info(f"AI Chat endpoint hit. Message length: {len(request.message)}, Has image: {request.image_base64 is not None}")

    result = await gemini_service.get_chat_response(
        message=request.message,
        history=request.history,
        image_base64=request.image_base64
    )

    # Map the raw dicts from Gemini into validated SuggestedAction models
    actions = []
    for a in result.get("suggested_actions", []):
        try:
            actions.append(
                SuggestedAction(
                    label=a.get("label", "Action"),
                    type=a.get("type", "CUSTOM"),
                    icon=a.get("icon", "check")
                )
            )
        except Exception as e:
            logger.warning(f"Skipping invalid action chip from AI: {a}. Error: {e}")

    return AIResponse(
        response=result.get("message", ""),
        suggested_actions=actions,
        quick_replies=result.get("quick_replies", [])
    )

@router.post("/analyze-places", response_model=AIResponse)
async def ai_analyze_places(request: AIAnalyzePlacesRequest):
    """AI-powered analysis of nearby wellness spots based on user context."""
    response_text = await gemini_service.analyze_places(request.user_context, request.places)
    return AIResponse(response=response_text)
