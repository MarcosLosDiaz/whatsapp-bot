import asyncio
import aiohttp
from azure.storage.queue.aio import QueueClient
from azure.storage.queue import TextBase64EncodePolicy
from azure.cosmos.aio import CosmosClient
import redis.asyncio as redis
from openai import AsyncOpenAI
from src.config import config

AIOHTTP_SESSION = None
COSMOS_CLIENT = None
COSMOS_STICKERS_CONTAINER = None
COSMOS_USER_STICKERS_CONTAINER = None
QUEUE_CLIENTS = {}
REDIS_POOL = None
OPENAI_CLIENT = None

_aiohttp_lock = None
_cosmos_lock = None
_queue_lock = None
_redis_lock = None
_openai_lock = None

async def get_aiohttp_session() -> aiohttp.ClientSession:
    global AIOHTTP_SESSION, _aiohttp_lock
    if _aiohttp_lock is None:
        _aiohttp_lock = asyncio.Lock()
    if AIOHTTP_SESSION is None:
        async with _aiohttp_lock:
            if AIOHTTP_SESSION is None:
                AIOHTTP_SESSION = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
    return AIOHTTP_SESSION

async def get_queue_client(queue_name: str) -> QueueClient:
    global _queue_lock
    if _queue_lock is None:
        _queue_lock = asyncio.Lock()
    if queue_name not in QUEUE_CLIENTS:
        async with _queue_lock:
            if queue_name not in QUEUE_CLIENTS:
                QUEUE_CLIENTS[queue_name] = QueueClient.from_connection_string(
                    config.AZURE_WEBJOBS_STORAGE, 
                    queue_name,
                    message_encode_policy=TextBase64EncodePolicy()
                )
    return QUEUE_CLIENTS[queue_name]

async def get_openai_client() -> AsyncOpenAI:
    global OPENAI_CLIENT, _openai_lock
    if _openai_lock is None:
        _openai_lock = asyncio.Lock()
    if OPENAI_CLIENT is None:
        async with _openai_lock:
            if OPENAI_CLIENT is None:
                OPENAI_CLIENT = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    return OPENAI_CLIENT

async def get_cosmos_stickers_container():
    global COSMOS_CLIENT, COSMOS_STICKERS_CONTAINER, COSMOS_USER_STICKERS_CONTAINER, _cosmos_lock
    if _cosmos_lock is None:
        _cosmos_lock = asyncio.Lock()
    if COSMOS_STICKERS_CONTAINER is None:
        async with _cosmos_lock:
            if COSMOS_STICKERS_CONTAINER is None:
                COSMOS_CLIENT = CosmosClient(config.COSMOS_DB_URL, credential=config.COSMOS_DB_KEY)
                db = COSMOS_CLIENT.get_database_client(config.COSMOS_DB_DATABASE)
                COSMOS_STICKERS_CONTAINER = db.get_container_client("stickers")
                COSMOS_USER_STICKERS_CONTAINER = db.get_container_client("user_stickers")
    return COSMOS_STICKERS_CONTAINER

async def get_cosmos_user_stickers_container():
    global COSMOS_CLIENT, COSMOS_STICKERS_CONTAINER, COSMOS_USER_STICKERS_CONTAINER, _cosmos_lock
    if _cosmos_lock is None:
        _cosmos_lock = asyncio.Lock()
    if COSMOS_USER_STICKERS_CONTAINER is None:
        async with _cosmos_lock:
            if COSMOS_USER_STICKERS_CONTAINER is None:
                COSMOS_CLIENT = CosmosClient(config.COSMOS_DB_URL, credential=config.COSMOS_DB_KEY)
                db = COSMOS_CLIENT.get_database_client(config.COSMOS_DB_DATABASE)
                COSMOS_STICKERS_CONTAINER = db.get_container_client("stickers")
                COSMOS_USER_STICKERS_CONTAINER = db.get_container_client("user_stickers")
    return COSMOS_USER_STICKERS_CONTAINER

async def get_redis_client() -> redis.Redis:
    global REDIS_POOL, _redis_lock
    if _redis_lock is None:
        _redis_lock = asyncio.Lock()
    if REDIS_POOL is None:
        async with _redis_lock:
            if REDIS_POOL is None:
                redis_url = config.REDIS_URL
                if not redis_url:
                    redis_url = f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}"
                REDIS_POOL = redis.ConnectionPool.from_url(redis_url, max_connections=config.REDIS_MAX_CONNECTIONS)
    return redis.Redis(connection_pool=REDIS_POOL)
