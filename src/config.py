import os
import sys
import logging

DEPLOY_ENV = os.environ.get("DEPLOY_ENV", "local")

def _load_config_store() -> dict:
    if DEPLOY_ENV in ["local", "local_terminal"]:
        return dict(os.environ)
    
    # Azure: pull from App Configuration, which transparently resolves Key Vault refs
    try:
        from azure.appconfiguration.provider import load
        from azure.identity import DefaultAzureCredential
        
        endpoint = os.environ.get("AZURE_APPCONFIG_ENDPOINT")
        if not endpoint:
            logging.warning("AZURE_APPCONFIG_ENDPOINT not set. Falling back to os.environ.")
            return dict(os.environ)
        
        credential = DefaultAzureCredential()
        config_store = load(
            endpoint=endpoint,
            credential=credential,
            keyvault_credential=credential,
            label_filter=DEPLOY_ENV,
        )
        return dict(config_store)
    except Exception as e:
        logging.error(f"Failed to load App Configuration: {type(e).__name__}. Falling back to os.environ.")
        return dict(os.environ)


class Config:
    def __init__(self):
        store = _load_config_store()
        
        self.DEPLOY_ENV = DEPLOY_ENV
        
        self.META_VERIFY_TOKEN = store.get("META_VERIFY_TOKEN", "default_verify_token")
        self.META_APP_SECRET = store.get("META_APP_SECRET")
        self.META_GRAPH_TOKEN = store.get("META_GRAPH_TOKEN")
        self.META_PHONE_ID = store.get("META_PHONE_ID")
        self.META_GRAPH_VERSION = store.get("META_GRAPH_VERSION", "v20.0")

        self.OPENAI_API_KEY = store.get("OPENAI_APIKEY")
        self.OPENAI_VLM_MODEL = store.get("OPENAI_VLM_MODEL", "gpt-4o-mini")
        self.OPENAI_EMBEDDING_MODEL = store.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

        self.COSMOS_DB_URL = store.get("COSMOS_DB_URL")
        self.COSMOS_DB_KEY = store.get("COSMOS_DB_KEY")
        self.COSMOS_DB_DATABASE = store.get("COSMOS_DB_DATABASE", "WhatsAppBot")

        self.REDIS_HOST = store.get("REDIS_HOST")
        self.REDIS_PORT = store.get("REDIS_PORT", "6379")
        self.REDIS_URL = store.get("REDIS_URL")
        self.REDIS_MAX_CONNECTIONS = int(store.get("REDIS_MAX_CONNECTIONS", "10"))
        self.REDIS_VECTOR_DIMENSIONS = int(store.get("REDIS_VECTOR_DIMENSIONS", "1536"))

        self.AZURE_WEBJOBS_STORAGE = store.get("AzureWebJobsStorage")
        
        self.PII_SALT = store.get("PII_SALT", "fallback_local_salt_12345")

    def validate(self):
        missing = []
        if not self.META_APP_SECRET: missing.append("META_APP_SECRET")
        if not self.META_GRAPH_TOKEN: missing.append("META_GRAPH_TOKEN")
        if not self.META_PHONE_ID: missing.append("META_PHONE_ID")
        if not self.OPENAI_API_KEY: missing.append("OPENAI_APIKEY")
        if not self.COSMOS_DB_URL: missing.append("COSMOS_DB_URL")
        # COSMOS_DB_KEY is optional (falls back to Managed Identity)
        if not self.REDIS_URL and not self.REDIS_HOST: missing.append("REDIS_URL or REDIS_HOST")
        if not self.AZURE_WEBJOBS_STORAGE: missing.append("AzureWebJobsStorage")

        if missing:
            logging.critical(f"Missing required environment variables: {', '.join(missing)}")
            if "pytest" not in sys.modules:
                sys.exit(1)

config = Config()
config.validate()
