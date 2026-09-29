import os
import asyncio
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

# Uniform async locks
_aiohttp_lock = asyncio.Lock()
_cosmos_lock = asyncio.Lock()
_queue_lock = asyncio.Lock()
_redis_lock = asyncio.Lock()
_openai_lock = asyncio.Lock()

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

async def get_openai_client() -> AsyncOpenAI:
    global OPENAI_CLIENT
    if OPENAI_CLIENT is None:
        async with _openai_lock:
            if OPENAI_CLIENT is None:
                OPENAI_CLIENT = AsyncOpenAI(api_key=os.environ['OPENAI_API_KEY'])
    return OPENAI_CLIENT

async def get_cosmos_container():
    global COSMOS_CLIENT, COSMOS_CONTAINER
    if COSMOS_CONTAINER is None:
        async with _cosmos_lock:
            if COSMOS_CONTAINER is None:
                db_name = os.environ.get('COSMOS_DB_DATABASE', 'WhatsAppBot')
                container_name = os.environ.get('COSMOS_DB_CONTAINER', 'stickers')
                COSMOS_CLIENT = CosmosClient(os.environ['COSMOS_DB_URL'], credential=os.environ['COSMOS_DB_KEY'])
                db = COSMOS_CLIENT.get_database_client(db_name)
                # Infrastructure explicitly requires the partition key to be /userId for upsert_item to work
                COSMOS_CONTAINER = db.get_container_client(container_name)
    return COSMOS_CONTAINER

async def get_redis_client() -> redis.Redis:
    global REDIS_POOL
    if REDIS_POOL is None:
        async with _redis_lock:
            if REDIS_POOL is None:
                redis_url = os.environ.get('REDIS_URL')
                if not redis_url:
                    host = os.environ.get('REDIS_HOST', 'localhost')
                    port = os.environ.get('REDIS_PORT', '6379')
                    redis_url = f"redis://{host}:{port}"
                REDIS_POOL = redis.ConnectionPool.from_url(redis_url)
    return redis.Redis(connection_pool=REDIS_POOL)

async def close_all_clients():
    """
    Gracefully tear down global singleton connections.
    Note: Azure Functions v2 Python programming model lacks native worker shutdown lifecycle hooks.
    This coroutine is provided to facilitate graceful teardown via manual invocation or future
    host-level lifecycle extensions, preventing 'Unclosed client session' memory leaks.
    """
    global AIOHTTP_SESSION, COSMOS_CLIENT, QUEUE_CLIENTS, REDIS_POOL
    if AIOHTTP_SESSION:
        await AIOHTTP_SESSION.close()
    if COSMOS_CLIENT:
        await COSMOS_CLIENT.close()
    for q in QUEUE_CLIENTS.values():
        await q.close()
    if REDIS_POOL:
        await REDIS_POOL.disconnect()
