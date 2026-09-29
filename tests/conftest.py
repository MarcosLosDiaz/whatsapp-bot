import pytest
import os

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("META_VERIFY_TOKEN", "test_verify_token")
    monkeypatch.setenv("META_GRAPH_TOKEN", "test_graph_token")
    monkeypatch.setenv("COSMOS_DB_URL", "https://localhost:8081")
    monkeypatch.setenv("COSMOS_DB_KEY", "test_key")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("OPENAI_API_KEY", "test_openai_key")
    monkeypatch.setenv("BING_API_KEY", "test_bing_key")
