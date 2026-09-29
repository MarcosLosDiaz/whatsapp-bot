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
        
        try:
            # Check if index exists and valid
            info = await client.ft('idx:stickers').info()
            # Basic validation that it's a vector index (in production you'd deeply diff the schema)
            if 'index_definition' not in info:
                raise ValueError("Index exists but schema invalid")
            INDEX_CREATED = True
        except Exception:
            # Index doesn't exist or is invalid, create it
            await client.ft('idx:stickers').create_index(fields=schema, definition=definition)
            logging.info("RediSearch index created.")
            INDEX_CREATED = True
    except Exception as e:
        logging.error(f"RediSearch index creation failed: {e}")
        raise # Fail fast if index creation legitimately fails so we don't silently ignore it
