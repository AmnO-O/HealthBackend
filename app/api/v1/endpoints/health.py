from fastapi import APIRouter
from datetime import datetime, timezone
from app.models.schemas import HealthCheckResponse

router = APIRouter()

@router.get("", response_model=HealthCheckResponse)
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "vitalis-ai-security-backend"
    }
