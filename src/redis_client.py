import os
import redis.asyncio as redis
import logging

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = os.environ.get('REDIS_PORT', '6379')

REDIS_POOL = None
INDEX_CREATED = False

def get_redis_client():
    global REDIS_POOL
    if not REDIS_POOL:
        REDIS_POOL = redis.ConnectionPool.from_url(
            f"redis://{REDIS_HOST}:{REDIS_PORT}"
        )
    return redis.Redis(connection_pool=REDIS_POOL)

async def ensure_index():
    global INDEX_CREATED
    if INDEX_CREATED:
        return
        
    client = get_redis_client()
    try:
        from redis.commands.search.field import VectorField, TagField
        from redis.commands.search.indexDefinition import IndexDefinition, IndexType
        
        schema = (
            TagField("userId"),
            TagField("stickerId"),
            VectorField("vector", "FLAT", {"TYPE": "FLOAT32", "DIM": 1536, "DISTANCE_METRIC": "COSINE"})
        )
        definition = IndexDefinition(prefix=["vector:"], index_type=IndexType.HASH)
        await client.ft('idx:stickers').create_index(fields=schema, definition=definition)
        logging.info("RediSearch index created.")
    except Exception as e:
        if "Index already exists" not in str(e):
            logging.warning(f"RediSearch index creation failed: {e}")
    finally:
        INDEX_CREATED = True
