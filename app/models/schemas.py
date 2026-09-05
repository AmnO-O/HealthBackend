from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

class ActionType(str, Enum):
    SAVE_TO_DIARY = "SAVE_TO_DIARY"
    VIEW_RECIPE = "VIEW_RECIPE"
    LOG_WATER = "LOG_WATER"
    SHOW_EXERCISES = "SHOW_EXERCISES"
    ASK_FOLLOWUP = "ASK_FOLLOWUP"
    CUSTOM = "CUSTOM"

class IconType(str, Enum):
    bookmark = "bookmark"
    menu_book = "menu_book"
    water_drop = "water_drop"
    fitness_center = "fitness_center"
    chat = "chat"
    check = "check"

class AIChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    image_base64: Optional[str] = Field(default=None, description="Optional base64 encoded image string")

class Place(BaseModel):
    name: str = Field(..., description="Name of the location")
    category: str = Field(default="Uncategorized", description="Category of the spot")
    address: Optional[str] = Field(default="Nearby area", description="Physical address")
    subtitle: Optional[str] = None

class AIAnalyzePlacesRequest(BaseModel):
    user_context: str
    places: List[Place]

class SuggestedAction(BaseModel):
    label: str = Field(description="Display text for the action button")
    type: ActionType = Field(description="Action type")
    icon: IconType = Field(default=IconType.check, description="Icon name")

class AIResponse(BaseModel):
    response: str
    suggested_actions: List[SuggestedAction] = Field(default_factory=list)
    quick_replies: List[str] = Field(default_factory=list)
    status: str = "success"

class HealthCheckResponse(BaseModel):
    status: str
    timestamp: str
    service: str
