import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.ingestion_worker import process_sticker
from azure.cosmos.exceptions import CosmosResourceNotFoundError

@pytest.mark.asyncio
@patch("src.ingestion_worker.save_to_redis")
@patch("src.ingestion_worker.save_to_cosmos")
@patch("src.ingestion_worker.generate_embeddings")
@patch("src.ingestion_worker.generate_description")
@patch("src.ingestion_worker.download_media")
@patch("src.ingestion_worker.ensure_index")
@patch("src.ingestion_worker.get_redis_client")
@patch("src.ingestion_worker.get_cosmos_container")
async def test_process_sticker(mock_cosmos, mock_get_redis, mock_ensure, mock_download, mock_desc, mock_embed, mock_save_cosmos, mock_redis):
    mock_download.return_value = b"fake_image_data"
    mock_desc.return_value = "A funny dog meme."
    mock_embed.return_value = [0.1, 0.2, 0.3]
    
    mock_redis_client = AsyncMock()
    mock_redis_client.exists.return_value = False
    mock_redis_client.set.return_value = True # Lock acquired
    mock_get_redis.return_value = mock_redis_client
    
    mock_container = AsyncMock()
    mock_container.read_item.side_effect = CosmosResourceNotFoundError()
    mock_cosmos.return_value = mock_container
    
    payload = {
        "user_id": "+15551234567",
        "sticker_id": "sticker123",
        "media_id": "media456"
    }
    
    await process_sticker(payload)
    
    mock_ensure.assert_called_once()
    mock_get_redis.assert_called_once()
    mock_download.assert_called_once()
    mock_desc.assert_called_once()
    mock_embed.assert_called_once()
    mock_save_cosmos.assert_called_once()
    mock_redis.assert_called_once()
