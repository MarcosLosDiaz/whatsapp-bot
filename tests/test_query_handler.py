import pytest
from unittest.mock import MagicMock, patch
from src.query_handler import handle_query

@patch("src.query_handler.ensure_index")
@patch("src.query_handler.requests.post")
@patch("src.query_handler.OpenAI")
@patch("src.query_handler.get_redis_client")
def test_handle_query(mock_redis_getter, mock_openai, mock_post, mock_ensure, monkeypatch):
    monkeypatch.setenv("META_PHONE_ID", "123456")
    monkeypatch.setenv("META_GRAPH_TOKEN", "token")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    
    mock_openai_instance = MagicMock()
    mock_openai.return_value = mock_openai_instance
    mock_embed_data = MagicMock()
    mock_embed_data.embedding = [0.1, 0.2, 0.3]
    mock_embed_response = MagicMock()
    mock_embed_response.data = [mock_embed_data]
    mock_openai_instance.embeddings.create.return_value = mock_embed_response
    
    mock_redis = MagicMock()
    mock_redis_getter.return_value = mock_redis
    mock_ft = MagicMock()
    mock_redis.ft.return_value = mock_ft
    mock_res = MagicMock()
    mock_doc = MagicMock()
    mock_doc.stickerId = "sticker123"
    mock_res.docs = [mock_doc]
    mock_ft.search.return_value = mock_res
    
    mock_post.return_value.status_code = 200
    
    payload = {
        "user_id": "+15551234567",
        "query": "funny dog"
    }
    
    handle_query(payload)
    
    mock_openai_instance.embeddings.create.assert_called_once()
    mock_ft.search.assert_called_once()
    mock_post.assert_called_once()
