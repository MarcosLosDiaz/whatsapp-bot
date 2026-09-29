import pytest
from unittest.mock import MagicMock, patch
from src.ingestion_worker import process_sticker

@patch("src.ingestion_worker.requests.get")
@patch("src.ingestion_worker.OpenAI")
@patch("src.ingestion_worker.CosmosClient")
@patch("src.ingestion_worker.redis.Redis")
def test_process_sticker(mock_redis, mock_cosmos, mock_openai, mock_get):
    # Setup mocks
    mock_get.return_value.status_code = 200
    mock_get.return_value.content = b"fake_image_data"
    
    mock_openai_instance = MagicMock()
    mock_openai.return_value = mock_openai_instance
    
    # Mock chat completion
    mock_message = MagicMock()
    mock_message.content = "A funny dog meme."
    mock_message.tool_calls = None
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_openai_instance.chat.completions.create.return_value = mock_response
    
    # Mock embeddings
    mock_embed_data = MagicMock()
    mock_embed_data.embedding = [0.1, 0.2, 0.3]
    mock_embed_response = MagicMock()
    mock_embed_response.data = [mock_embed_data]
    mock_openai_instance.embeddings.create.return_value = mock_embed_response
    
    # Run processor
    payload = {
        "user_id": "15551234567",
        "sticker_id": "sticker123",
        "media_id": "media456"
    }
    
    process_sticker(payload)
    
    # Assertions
    assert mock_get.call_count == 2
    mock_openai_instance.chat.completions.create.assert_called_once()
    mock_openai_instance.embeddings.create.assert_called_once()
    mock_cosmos.return_value.get_database_client.return_value.get_container_client.return_value.upsert_item.assert_called_once()
    mock_redis.from_url.return_value.hset.assert_called_once()

