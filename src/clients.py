import os
import asyncio
import threading
import aiohttp
from azure.storage.queue.aio import QueueClient
from azure.storage.queue import TextBase64EncodePolicy
from azure.cosmos.aio import CosmosClient
import redis.asyncio as redis
from openai import AsyncOpenAI

AIOHTTP_SESSION = None
COSMOS_CLIENT = None
COSMOS_CONTAINER = None
QUEUE_CLIENTS = {}
REDIS_POOL = None
OPENAI_CLIENT = None

# Locks to prevent race conditions during cold starts
_aiohttp_lock = asyncio.Lock()
_cosmos_lock = asyncio.Lock()
_queue_lock = asyncio.Lock()
_redis_lock = threading.Lock()
_openai_lock = threading.Lock()

async def get_aiohttp_session() -> aiohttp.ClientSession:
    global AIOHTTP_SESSION
    if AIOHTTP_SESSION is None:
        async with _aiohttp_lock:
            if AIOHTTP_SESSION is None:
                AIOHTTP_SESSION = aiohttp.ClientSession()
    return AIOHTTP_SESSION

async def get_queue_client(queue_name: str) -> QueueClient:
    global QUEUE_CLIENTS
    if queue_name not in QUEUE_CLIENTS:
        async with _queue_lock:
            if queue_name not in QUEUE_CLIENTS:
                conn_str = os.environ['AzureWebJobsStorage'] # Eager fail if missing
                QUEUE_CLIENTS[queue_name] = QueueClient.from_connection_string(
                    conn_str, 
                    queue_name,
                    message_encode_policy=TextBase64EncodePolicy()
                )
    return QUEUE_CLIENTS[queue_name]

def get_openai_client() -> AsyncOpenAI:
    global OPENAI_CLIENT
    if OPENAI_CLIENT is None:
        with _openai_lock:
            if OPENAI_CLIENT is None:
                OPENAI_CLIENT = AsyncOpenAI(api_key=os.environ['OPENAI_API_KEY'])
    return OPENAI_CLIENT

async def get_cosmos_container():
    global COSMOS_CLIENT, COSMOS_CONTAINER
    if COSMOS_CONTAINER is None:
        async with _cosmos_lock:
            if COSMOS_CONTAINER is None:
                COSMOS_CLIENT = CosmosClient(os.environ['COSMOS_DB_URL'], credential=os.environ['COSMOS_DB_KEY'])
                db = COSMOS_CLIENT.get_database_client('WhatsAppBot')
                COSMOS_CONTAINER = db.get_container_client('stickers')
    return COSMOS_CONTAINER

def get_redis_client() -> redis.Redis:
    global REDIS_POOL
    if REDIS_POOL is None:
        with _redis_lock:
            if REDIS_POOL is None:
                redis_url = os.environ.get('REDIS_URL')
                if not redis_url:
                    host = os.environ.get('REDIS_HOST', 'localhost')
                    port = os.environ.get('REDIS_PORT', '6379')
                    redis_url = f"redis://{host}:{port}"
                REDIS_POOL = redis.ConnectionPool.from_url(redis_url)
    return redis.Redis(connection_pool=REDIS_POOL)
