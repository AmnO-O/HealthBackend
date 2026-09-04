import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "vitalis-ai-proxy"

def test_api_v1_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "vitalis-ai-security-backend"
    assert "timestamp" in data

def test_ai_ping_endpoint():
    response = client.get("/api/v1/ai/ping")
    assert response.status_code == 200
    assert response.json()["status"] == "awake"

def test_ai_chat_endpoint_schema():
    """Verify AI chat endpoint accepts valid request and returns structured response."""
    mock_chat_response = {
        "message": "Drink at least 2 liters of water daily to stay hydrated.",
        "suggested_actions": [
            {"label": "Log Water", "type": "LOG_WATER", "icon": "water_drop"}
        ],
        "quick_replies": ["How much water after exercise?"]
    }

    with patch("app.services.gemini_service.gemini_service.get_chat_response", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = mock_chat_response

        payload = {
            "message": "How much water should I drink?",
            "history": []
        }
        response = client.post("/api/v1/ai/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "Drink at least 2 liters" in data["response"]
        assert len(data["suggested_actions"]) == 1
        assert data["suggested_actions"][0]["type"] == "LOG_WATER"
        assert len(data["quick_replies"]) == 1

def test_ai_analyze_places_endpoint():
    """Verify AI analyze-places endpoint processes places context."""
    with patch("app.services.gemini_service.gemini_service.analyze_places", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = "The nearby pharmacy is recommended for wellness supplies."

        payload = {
            "user_context": "Looking for first aid and hydration drinks",
            "places": [
                {
                    "name": "Central Pharmacy",
                    "category": "PHARMACY",
                    "address": "123 Main St"
                }
            ]
        }
        response = client.post("/api/v1/ai/analyze-places", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "Central Pharmacy" in data["response"] or "recommended" in data["response"]
