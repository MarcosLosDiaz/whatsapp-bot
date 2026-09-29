import logging
from src.clients import get_redis_client

INDEX_CREATED = False

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
        INDEX_CREATED = True
    except Exception as e:
        if "Index already exists" in str(e):
            INDEX_CREATED = True
        else:
            logging.error(f"RediSearch index creation failed: {e}")
            raise # Fail fast if index creation legitimately fails so we don't silently ignore it
