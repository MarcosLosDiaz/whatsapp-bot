import os

class Config:
    # Fail fast eagerly at module import
    META_VERIFY_TOKEN = os.environ['META_VERIFY_TOKEN']
    META_APP_SECRET = os.environ['META_APP_SECRET']
    META_GRAPH_TOKEN = os.environ['META_GRAPH_TOKEN']
    META_PHONE_ID = os.environ['META_PHONE_ID']
    OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
    COSMOS_DB_URL = os.environ['COSMOS_DB_URL']
    COSMOS_DB_KEY = os.environ['COSMOS_DB_KEY']
    AZURE_WEBJOBS_STORAGE = os.environ['AzureWebJobsStorage']

    # Optional configs with defaults
    REDIS_URL = os.environ.get('REDIS_URL')
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = os.environ.get('REDIS_PORT', '6379')
    REDIS_MAX_CONNECTIONS = int(os.environ.get('REDIS_MAX_CONNECTIONS', '10'))
    REDIS_VECTOR_DIMENSIONS = int(os.environ.get('REDIS_VECTOR_DIMENSIONS', '1536'))
    
    COSMOS_DB_DATABASE = os.environ.get('COSMOS_DB_DATABASE', 'WhatsAppBot')
    COSMOS_DB_CONTAINER = os.environ.get('COSMOS_DB_CONTAINER', 'stickers')
    
    OPENAI_VLM_MODEL = os.environ.get('OPENAI_VLM_MODEL', 'gpt-4o-mini')
    OPENAI_EMBEDDING_MODEL = os.environ.get('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
    META_GRAPH_VERSION = os.environ.get('META_GRAPH_VERSION', 'v18.0')

config = Config()
