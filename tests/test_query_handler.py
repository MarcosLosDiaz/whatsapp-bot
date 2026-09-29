import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.query_handler import handle_query

@pytest.mark.asyncio
@patch("src.query_handler.ensure_index")
@patch("src.query_handler.get_aiohttp_session")
@patch("src.query_handler.AsyncOpenAI")
@patch("src.query_handler.get_redis_client")
async def test_handle_query(mock_redis_getter, mock_openai, mock_get_session, mock_ensure):
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session
    
    mock_openai_instance = AsyncMock()
    mock_openai.return_value = mock_openai_instance
    mock_embed_data = MagicMock()
    mock_embed_data.embedding = [0.1, 0.2, 0.3]
    mock_embed_response = MagicMock()
    mock_embed_response.data = [mock_embed_data]
    mock_openai_instance.embeddings.create.return_value = mock_embed_response
    
    mock_redis = MagicMock()
    mock_redis_getter.return_value = mock_redis
    mock_ft = AsyncMock()
    mock_redis.ft.return_value = mock_ft
    mock_res = MagicMock()
    mock_doc = MagicMock()
    mock_doc.stickerId = "sticker123"
    mock_res.docs = [mock_doc]
    mock_ft.search.return_value = mock_res
    
    mock_resp = AsyncMock()
    mock_resp.raise_for_status = MagicMock()
    mock_session.post.return_value.__aenter__.return_value = mock_resp
    
    payload = {
        "user_id": "+15551234567",
        "query": "funny dog"
    }
    
    await handle_query(payload)
    
    mock_openai_instance.embeddings.create.assert_called_once()
    mock_ft.search.assert_called_once()
    mock_session.post.assert_called_once()
