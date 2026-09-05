import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.gemini_service import GeminiService

@pytest.mark.asyncio
async def test_analyze_places_with_missing_fields():
    """Verify analyze_places handles Place objects with default/missing fields correctly."""
    from app.models.schemas import Place

    with patch("app.services.gemini_service.settings") as mock_settings:
        mock_settings.gemini_api_keys = ["key1"]
        mock_settings.GEMINI_MODEL_NAME = "gemini-3.5-flash-lite"

        service = GeminiService()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Analysis result"
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        service._clients = {"key1": mock_client}

        # Test with missing optional fields (address, subtitle)
        places = [
            Place(name="Central Clinic", category="CLINIC")
        ]

        result = await service.analyze_places("Feeling sick", places)
        assert result == "Analysis result"

        # Verify the prompt string construction
        args, kwargs = mock_client.aio.models.generate_content.call_args
        prompt = kwargs["contents"]
        assert "Central Clinic" in prompt
        assert "CLINIC" in prompt
        assert "Nearby area" in prompt # Default address

@pytest.mark.asyncio
async def test_get_chat_response_handles_safety_blocked():
    """Verify get_chat_response returns friendly message when response.text is empty (SAFETY block)."""

    with patch("app.services.gemini_service.settings") as mock_settings:
        mock_settings.gemini_api_keys = ["key1"]
        mock_settings.GEMINI_MODEL_NAME = "gemini-3.5-flash-lite"

        service = GeminiService()
        mock_client = MagicMock()

        # Simulate blocked response
        mock_response = MagicMock()
        mock_response.text = None # response.text is None when blocked
        mock_candidate = MagicMock()
        mock_candidate.finish_reason = "SAFETY"
        mock_response.candidates = [mock_candidate]

        mock_chat = MagicMock()
        mock_chat.send_message = AsyncMock(return_value=mock_response)
        mock_client.aio.chats.create.return_value = mock_chat
        service._clients = {"key1": mock_client}

        result = await service.get_chat_response("Something dangerous", history=[])

        assert "flagged by safety filters" in result["message"]
        assert result["suggested_actions"] == []
        assert "try a different question" in result["quick_replies"][0]

@pytest.mark.asyncio
async def test_ai_chat_handles_invalid_suggested_actions():
    """Verify that the AI chat endpoint skips invalid action chips instead of crashing."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    mock_chat_response = {
        "message": "Here is a valid tip.",
        "suggested_actions": [
            {"label": "Valid", "type": "SAVE_TO_DIARY", "icon": "bookmark"},
            {"label": "Invalid", "type": "HACK_SYSTEM", "icon": "skull"} # Invalid Enum values
        ],
        "quick_replies": []
    }

    with patch("app.services.gemini_service.gemini_service.get_chat_response", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = mock_chat_response

        payload = {"message": "Give me a tip", "history": []}
        response = client.post("/api/v1/ai/chat", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Should only have 1 valid action, the invalid one should be skipped
        assert len(data["suggested_actions"]) == 1
        assert data["suggested_actions"][0]["label"] == "Valid"
