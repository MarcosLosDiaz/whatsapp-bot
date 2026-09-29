import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.ingestion_worker import process_sticker

@pytest.mark.asyncio
@patch("src.ingestion_worker.ensure_index")
@patch("src.ingestion_worker.aiohttp.ClientSession.get")
@patch("src.ingestion_worker.AsyncOpenAI")
@patch("src.ingestion_worker.CosmosClient")
@patch("src.ingestion_worker.get_redis_client")
async def test_process_sticker(mock_redis_getter, mock_cosmos, mock_openai, mock_get, mock_ensure, monkeypatch):
    monkeypatch.setenv("META_GRAPH_TOKEN", "token")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    monkeypatch.setenv("COSMOS_DB_URL", "url")
    monkeypatch.setenv("COSMOS_DB_KEY", "key")

    mock_resp1 = AsyncMock()
    mock_resp1.raise_for_status = MagicMock()
    mock_resp1.json.return_value = {"url": "http://image"}
    
    mock_resp2 = AsyncMock()
    mock_resp2.raise_for_status = MagicMock()
    mock_resp2.headers = {'Content-Type': 'image/jpeg'}
    mock_resp2.read.return_value = b"fake_image_data"
    
    # Return mock_resp1 on first call, mock_resp2 on second
    mock_get.side_effect = [AsyncMock(__aenter__=AsyncMock(return_value=mock_resp1)), AsyncMock(__aenter__=AsyncMock(return_value=mock_resp2))]
    
    mock_openai_instance = AsyncMock()
    mock_openai.return_value = mock_openai_instance
    mock_message = MagicMock()
    mock_message.content = "A funny dog meme."
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_chat_response = MagicMock()
    mock_chat_response.choices = [mock_choice]
    mock_openai_instance.chat.completions.create.return_value = mock_chat_response
    
    mock_embed_data = MagicMock()
    mock_embed_data.embedding = [0.1, 0.2, 0.3]
    mock_embed_response = MagicMock()
    mock_embed_response.data = [mock_embed_data]
    mock_openai_instance.embeddings.create.return_value = mock_embed_response
    
    payload = {
        "user_id": "+15551234567",
        "sticker_id": "sticker123",
        "media_id": "media456"
    }
    
    mock_redis = MagicMock()
    mock_redis_getter.return_value = mock_redis
    
    await process_sticker(payload)
    
    assert mock_get.call_count == 2
    mock_openai_instance.chat.completions.create.assert_called_once()
    mock_openai_instance.embeddings.create.assert_called_once()
    mock_cosmos.return_value.get_database_client.return_value.get_container_client.return_value.upsert_item.assert_called_once()
    mock_redis.hset.assert_called_once()
