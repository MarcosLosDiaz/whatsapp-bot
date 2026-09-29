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
                # 15s timeout to prevent hanging retries in tenacity
                AIOHTTP_SESSION = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
    return AIOHTTP_SESSION

async def get_queue_client(queue_name: str) -> QueueClient:
    global QUEUE_CLIENTS, _queue_lock
    if _queue_lock is None:
        _queue_lock = asyncio.Lock()
    if queue_name not in QUEUE_CLIENTS:
        async with _queue_lock:
            if queue_name not in QUEUE_CLIENTS:
                conn_str = os.environ['AzureWebJobsStorage']
                QUEUE_CLIENTS[queue_name] = QueueClient.from_connection_string(
                    conn_str, 
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
                OPENAI_CLIENT = AsyncOpenAI(api_key=os.environ['OPENAI_API_KEY'])
    return OPENAI_CLIENT

async def get_cosmos_container():
    global COSMOS_CLIENT, COSMOS_CONTAINER, _cosmos_lock
    if _cosmos_lock is None:
        _cosmos_lock = asyncio.Lock()
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
    global REDIS_POOL, _redis_lock
    if _redis_lock is None:
        _redis_lock = asyncio.Lock()
    if REDIS_POOL is None:
        async with _redis_lock:
            if REDIS_POOL is None:
                redis_url = os.environ.get('REDIS_URL')
                if not redis_url:
                    host = os.environ.get('REDIS_HOST', 'localhost')
                    port = os.environ.get('REDIS_PORT', '6379')
                    redis_url = f"redis://{host}:{port}"
                max_conn = int(os.environ.get('REDIS_MAX_CONNECTIONS', '10'))
                REDIS_POOL = redis.ConnectionPool.from_url(redis_url, max_connections=max_conn)
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
