import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_ai_chat_with_image_schema():
    """Verify AI chat endpoint accepts image_base64 in the payload."""
    mock_chat_response = {
        "message": "That looks like a healthy salad!",
        "suggested_actions": [
            {"label": "Save to Diary", "type": "SAVE_TO_DIARY", "icon": "bookmark"}
        ],
        "quick_replies": ["What are the ingredients?"]
    }

    with patch("app.services.gemini_service.gemini_service.get_chat_response", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = mock_chat_response

        # Sample base64 string (a tiny 1x1 black dot PNG)
        sample_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        payload = {
            "message": "What is in this photo?",
            "history": [],
            "image_base64": sample_b64
        }

        response = client.post("/api/v1/ai/chat", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Verify mock was called with the image data
        mock_gemini.assert_called_once()
        args, kwargs = mock_gemini.call_args
        assert kwargs["image_base64"] == sample_b64

        assert "healthy salad" in data["response"]
        assert data["suggested_actions"][0]["type"] == "SAVE_TO_DIARY"

def test_ai_chat_without_image_regression():
    """Ensure the text-only flow still works perfectly (Regression test)."""
    mock_chat_response = {
        "message": "Hello, how can I help you?",
        "suggested_actions": [],
        "quick_replies": []
    }

    with patch("app.services.gemini_service.gemini_service.get_chat_response", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = mock_chat_response

        payload = {
            "message": "Hello",
            "history": []
        }

        response = client.post("/api/v1/ai/chat", json=payload)

        assert response.status_code == 200
        mock_gemini.assert_called_once()
        args, kwargs = mock_gemini.call_args
        assert kwargs["image_base64"] is None

def test_ai_chat_with_invalid_base64():
    """Verify AI chat handles potentially corrupt base64 gracefully."""
    mock_chat_response = {
        "message": "I couldn't read that image clearly.",
        "suggested_actions": [],
        "quick_replies": []
    }

    with patch("app.services.gemini_service.gemini_service.get_chat_response", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = mock_chat_response

        payload = {
            "message": "What is this?",
            "history": [],
            "image_base64": "not-a-valid-base64-string!!!"
        }

        response = client.post("/api/v1/ai/chat", json=payload)
        assert response.status_code == 200
        assert "couldn't read" in response.json()["response"]
