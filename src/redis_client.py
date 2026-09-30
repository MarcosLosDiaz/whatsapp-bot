import logging
import asyncio
from src.clients import get_redis_client
from src.config import config

INDEX_CREATED = False

async def ensure_index():
    global INDEX_CREATED
    if INDEX_CREATED:
        return
            
    client = await get_redis_client()
    try:
        from redis.commands.search.field import VectorField, TagField
        from redis.commands.search.indexDefinition import IndexDefinition, IndexType
        
        schema = (
            TagField("userId"),
            TagField("stickerId"),
            VectorField("vector", "FLAT", {"TYPE": "FLOAT32", "DIM": config.REDIS_VECTOR_DIMENSIONS, "DISTANCE_METRIC": "COSINE"})
        )
        definition = IndexDefinition(prefix=["vector:"], index_type=IndexType.HASH)
        
        try:
            info = await client.ft('idx:stickers').info()
            if 'index_definition' not in info:
                raise ValueError("Index exists but schema invalid")
            INDEX_CREATED = True
        except Exception:
            try:
                await client.ft('idx:stickers').create_index(fields=schema, definition=definition)
                logging.info("RediSearch index created.")
                INDEX_CREATED = True
            except Exception as e:
                if "Index already exists" in str(e):
                    INDEX_CREATED = True
                else:
                    raise
    except Exception as e:
        logging.error(f"RediSearch index validation/creation failed: {e}")
        raise
