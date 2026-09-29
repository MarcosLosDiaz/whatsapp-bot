import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.query_handler import handle_query

@pytest.mark.asyncio
@patch("src.query_handler.send_text_message")
@patch("src.query_handler.send_sticker")
@patch("src.query_handler.get_redis_client")
@patch("src.query_handler.get_query_embedding")
@patch("src.query_handler.ensure_index")
async def test_handle_query(mock_ensure, mock_get_embed, mock_get_redis, mock_send_sticker, mock_send_text):
    mock_get_embed.return_value = [0.1, 0.2, 0.3]
    
    mock_redis = MagicMock()
    mock_get_redis.return_value = mock_redis
    
    mock_ft = MagicMock()
    mock_redis.ft.return_value = mock_ft
    mock_res = MagicMock()
    mock_doc = MagicMock()
    mock_doc.stickerId = "sticker123"
    mock_res.docs = [mock_doc]
    
    mock_search = AsyncMock()
    mock_search.return_value = mock_res
    mock_ft.search = mock_search
    
    payload = {
        "user_id": "+15551234567",
        "query": "funny dog"
    }
    
    await handle_query(payload)
    
    mock_ensure.assert_called_once()
    mock_get_embed.assert_called_once()
    mock_ft.search.assert_called_once()
    mock_send_sticker.assert_called_once()
    mock_send_text.assert_not_called()
