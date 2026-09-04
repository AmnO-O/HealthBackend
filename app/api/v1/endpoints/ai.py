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
    """Health-focused AI chat powered by Gemini with structured action chips."""
    logger.info(f"AI Chat endpoint hit with message: {request.message[:50]}...")
    result = await gemini_service.get_chat_response(request.message, request.history)

    # Map the raw dicts from Gemini into validated SuggestedAction models
    actions = [
        SuggestedAction(
            label=a.get("label", "Action"),
            type=a.get("type", "CUSTOM"),
            icon=a.get("icon", "check")
        )
        for a in result.get("suggested_actions", [])
    ]

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
