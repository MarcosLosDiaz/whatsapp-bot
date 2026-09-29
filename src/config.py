import os
import sys
import logging

class Config:
    def __init__(self):
        self.META_VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "default_verify_token")
        self.META_APP_SECRET = os.environ.get("META_APP_SECRET")
        self.META_GRAPH_TOKEN = os.environ.get("META_GRAPH_TOKEN")
        self.META_PHONE_ID = os.environ.get("META_PHONE_ID")
        self.META_GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v20.0")

        self.OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
        self.OPENAI_VLM_MODEL = os.environ.get("OPENAI_VLM_MODEL", "gpt-4o-mini")
        self.OPENAI_EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

        self.COSMOS_DB_URL = os.environ.get("COSMOS_DB_URL")
        self.COSMOS_DB_KEY = os.environ.get("COSMOS_DB_KEY")
        self.COSMOS_DB_DATABASE = os.environ.get("COSMOS_DB_DATABASE", "WhatsAppBot")

        self.REDIS_HOST = os.environ.get("REDIS_HOST")
        self.REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
        self.REDIS_URL = os.environ.get("REDIS_URL")
        self.REDIS_MAX_CONNECTIONS = int(os.environ.get("REDIS_MAX_CONNECTIONS", "10"))
        self.REDIS_VECTOR_DIMENSIONS = int(os.environ.get("REDIS_VECTOR_DIMENSIONS", "1536"))

        self.AZURE_WEBJOBS_STORAGE = os.environ.get("AzureWebJobsStorage")
        
        self.PII_SALT = os.environ.get("PII_SALT", "fallback_local_salt_12345")

    def validate(self):
        missing = []
        if not self.META_APP_SECRET: missing.append("META_APP_SECRET")
        if not self.META_GRAPH_TOKEN: missing.append("META_GRAPH_TOKEN")
        if not self.META_PHONE_ID: missing.append("META_PHONE_ID")
        if not self.OPENAI_API_KEY: missing.append("OPENAI_API_KEY")
        if not self.COSMOS_DB_URL: missing.append("COSMOS_DB_URL")
        if not self.COSMOS_DB_KEY: missing.append("COSMOS_DB_KEY")
        if not self.REDIS_URL and not self.REDIS_HOST: missing.append("REDIS_URL or REDIS_HOST")
        if not self.AZURE_WEBJOBS_STORAGE: missing.append("AzureWebJobsStorage")

        if missing:
            logging.critical(f"Missing required environment variables: {', '.join(missing)}")
            if "pytest" not in sys.modules:
                sys.exit(1)

config = Config()
config.validate()
