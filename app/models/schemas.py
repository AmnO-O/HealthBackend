from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class AIChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = Field(default_factory=list)

class AIAnalyzePlacesRequest(BaseModel):
    user_context: str
    places: List[Dict[str, Any]]

class SuggestedAction(BaseModel):
    label: str = Field(description="Display text for the action button")
    type: str = Field(description="Action type: SAVE_TO_DIARY, VIEW_RECIPE, LOG_WATER, ASK_FOLLOWUP, SHOW_EXERCISES, CUSTOM")
    icon: str = Field(default="check", description="Icon name: bookmark, menu_book, water_drop, chat, fitness_center, check")

class AIResponse(BaseModel):
    response: str
    suggested_actions: List[SuggestedAction] = Field(default_factory=list)
    quick_replies: List[str] = Field(default_factory=list)
    status: str = "success"

class HealthCheckResponse(BaseModel):
    status: str
    timestamp: str
    service: str
