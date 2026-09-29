import os
import pytest

# Ensure eager env vars exist before modules are imported
os.environ['OPENAI_API_KEY'] = 'test'
os.environ['COSMOS_DB_URL'] = 'test'
os.environ['COSMOS_DB_KEY'] = 'test'
os.environ['META_GRAPH_TOKEN'] = 'test'
os.environ['META_PHONE_ID'] = 'test'
os.environ['META_VERIFY_TOKEN'] = 'test'
os.environ['META_APP_SECRET'] = 'test'
os.environ['AzureWebJobsStorage'] = 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net'
os.environ['REDIS_HOST'] = 'test'
os.environ['REDIS_PORT'] = '6379'

@pytest.fixture(autouse=True)
def mock_env():
    pass
