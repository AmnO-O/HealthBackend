import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.gemini_service import GeminiService
from google.genai import errors

class MockAPIError(Exception):
    def __init__(self, message, code):
        self.message = message
        self.code = code
    def __str__(self):
        return self.message

@pytest.mark.asyncio
async def test_gemini_service_rotates_on_429():
    """Verify that GeminiService rotates to the next key when a 429 error occurs."""

    # Mock settings to have two keys
    mock_keys = ["key1", "key2"]

    with patch("app.services.gemini_service.settings") as mock_settings:
        mock_settings.gemini_api_keys = mock_keys
        mock_settings.GEMINI_MODEL_NAME = "gemini-3.5-flash-lite"

        # Create a fresh service instance for this test
        service = GeminiService()
        assert service.api_keys == mock_keys
        assert service._current_key_index == 0

        # Mock the genai.Client
        mock_client1 = MagicMock()
        mock_client2 = MagicMock()

        # Mock chat creation for client 1 to FAIL with 429
        mock_chat1 = MagicMock()
        mock_chat1.send_message = AsyncMock(side_effect=MockAPIError(
            message="Quota exceeded",
            code=429
        ))
        mock_client1.aio.chats.create.return_value = mock_chat1

        # Mock chat creation for client 2 to SUCCEED
        mock_chat2 = MagicMock()
        mock_chat2.send_message = AsyncMock(return_value=MagicMock(text='{"message": "Success from key 2", "suggested_actions": [], "quick_replies": []}'))
        mock_client2.aio.chats.create.return_value = mock_chat2

        # Set the cached clients
        service._clients = {"key1": mock_client1, "key2": mock_client2}

        # Call the service
        result = await service.get_chat_response("Hello", history=[])

        # Assertions
        assert result["message"] == "Success from key 2"
        assert service._current_key_index == 1 # Verified rotation stayed at 1
        assert mock_chat1.send_message.called
        assert mock_chat2.send_message.called

@pytest.mark.asyncio
async def test_gemini_service_fails_fast_on_400():
    """Verify that GeminiService does NOT rotate and fails immediately on a 400 error."""

    mock_keys = ["key1", "key2"]

    with patch("app.services.gemini_service.settings") as mock_settings:
        mock_settings.gemini_api_keys = mock_keys
        mock_settings.GEMINI_MODEL_NAME = "gemini-3.5-flash-lite"

        service = GeminiService()

        mock_client1 = MagicMock()
        mock_chat1 = MagicMock()
        # Mock 400 Bad Request (e.g. invalid prompt)
        mock_chat1.send_message = AsyncMock(side_effect=MockAPIError(
            message="Invalid argument",
            code=400
        ))
        mock_client1.aio.chats.create.return_value = mock_chat1

        service._clients = {"key1": mock_client1}

        result = await service.get_chat_response("Bad Prompt", history=[])

        # Assertions
        assert "Invalid argument" in result["message"]
        assert service._current_key_index == 0 # Index should NOT have moved
        assert mock_chat1.send_message.call_count == 1

@pytest.mark.asyncio
async def test_gemini_service_exhausts_all_keys():
    """Verify that if all keys return 429, the service returns the final error."""

    mock_keys = ["key1", "key2"]

    with patch("app.services.gemini_service.settings") as mock_settings:
        mock_settings.gemini_api_keys = mock_keys
        mock_settings.GEMINI_MODEL_NAME = "gemini-3.5-flash-lite"

        service = GeminiService()

        mock_client1 = MagicMock()
        mock_chat1 = MagicMock()
        mock_chat1.send_message = AsyncMock(side_effect=MockAPIError(message="Quota 1", code=429))
        mock_client1.aio.chats.create.return_value = mock_chat1

        mock_client2 = MagicMock()
        mock_chat2 = MagicMock()
        mock_chat2.send_message = AsyncMock(side_effect=MockAPIError(message="Quota 2", code=429))
        mock_client2.aio.chats.create.return_value = mock_chat2

        service._clients = {"key1": mock_client1, "key2": mock_client2}

        result = await service.get_chat_response("Hello", history=[])

        assert "Quota 2" in result["message"]
        assert service._current_key_index == 0 # Rotated key1 -> key2 -> back to key1 (0)
        assert mock_chat1.send_message.call_count == 1
        assert mock_chat2.send_message.call_count == 1
