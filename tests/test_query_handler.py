import pytest
from unittest.mock import MagicMock, patch
from src.query_handler import handle_query

@patch("src.query_handler.requests.post")
@patch("src.query_handler.OpenAI")
@patch("src.query_handler.redis.Redis")
def test_handle_query(mock_redis, mock_openai, mock_post):
    # Mock embeddings
    mock_openai_instance = MagicMock()
    mock_openai.return_value = mock_openai_instance
    mock_embed_data = MagicMock()
    mock_embed_data.embedding = [0.1, 0.2, 0.3]
    mock_embed_response = MagicMock()
    mock_embed_response.data = [mock_embed_data]
    mock_openai_instance.embeddings.create.return_value = mock_embed_response
    
    # Mock Redis search (simplistic test double)
    # We pretend Redis returned a matching stickerId
    mock_redis.from_url.return_value.hgetall.return_value = {
        b"vector": b"[0.1, 0.2, 0.3]",
        b"stickerId": b"sticker123"
    }
    mock_redis.from_url.return_value.keys.return_value = [b"vector:15551234567:sticker123"]
    
    mock_post.return_value.status_code = 200
    
    payload = {
        "user_id": "15551234567",
        "query": "funny dog"
    }
    
    handle_query(payload)
    
    # Assertions
    mock_openai_instance.embeddings.create.assert_called_once()
    mock_redis.from_url.return_value.keys.assert_called_once()
    mock_post.assert_called_once()
    
    # Check Meta API payload
    args, kwargs = mock_post.call_args
    assert "messaging_product" in kwargs['json']
    assert kwargs['json']['type'] == "sticker"

