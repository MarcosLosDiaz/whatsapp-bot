import os
import redis
import logging

REDIS_POOL = None

def get_redis_client():
    global REDIS_POOL
    if not REDIS_POOL:
        REDIS_POOL = redis.ConnectionPool.from_url(
            f"redis://{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', '6379')}"
        )
    return redis.Redis(connection_pool=REDIS_POOL)

def ensure_index():
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
        client.ft('idx:stickers').create_index(fields=schema, definition=definition)
        logging.info("RediSearch index created.")
    except Exception as e:
        if "Index already exists" not in str(e):
            logging.warning(f"RediSearch index creation failed: {e}")
