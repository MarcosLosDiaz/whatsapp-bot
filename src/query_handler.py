from src.messaging import get_messaging_provider
import logging
import struct
import hashlib
import re
import aiohttp
from openai import APIConnectionError, RateLimitError, BadRequestError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from src.redis_client import ensure_index, INDEX_CREATED
from src.clients import get_aiohttp_session, get_openai_client, get_redis_client
from src.schemas import QueryQueuePayload
from src.config import config

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type(aiohttp.ClientError))



@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type((APIConnectionError, RateLimitError)))
async def get_query_embedding(query: str):
    client = await get_openai_client()
    embed_response = await client.embeddings.create(
        model=config.OPENAI_EMBEDDING_MODEL,
        input=query
    )
    return embed_response.data[0].embedding

def hash_pii(data: str) -> str:
    return hashlib.sha256((data + config.PII_SALT).encode('utf-8')).hexdigest()[:8]

async def handle_query(payload_dict: dict):
    payload = QueryQueuePayload.model_validate(payload_dict)
    
    user_hash = hash_pii(payload.user_id)
    logging.info(f"Handling query [REDACTED] for user {user_hash}")
    
    if not INDEX_CREATED:
        await ensure_index()
    
    # Strictly alphanumeric normalization to prevent NoSQL RediSearch injection
    normalized_user = re.sub(r'[^a-zA-Z0-9]', '', payload.user_id)
        
    try:
        query_embedding = await get_query_embedding(payload.query)
    except BadRequestError:
        logging.error(f"Semantic API failure on query for user {user_hash}")
        await get_messaging_provider().send_text(payload.user_id, "I couldn't process your query due to a policy restriction.")
        return
        
    packed_embedding = struct.pack(f'<{len(query_embedding)}f', *query_embedding)
    
    redis_client = await get_redis_client()
    
    best_sticker_id = None
    debug_info = None
    try:
        from redis.commands.search.query import Query
        q = Query(f'(@userId:{{{normalized_user}}})=>[KNN 1 @vector $vec as score]').sort_by('score').return_fields('stickerId', 'score').dialect(2)
        res = await redis_client.ft('idx:stickers').search(q, query_params={'vec': packed_embedding})
        if res.docs:
            sticker_val = res.docs[0].stickerId
            best_sticker_id = sticker_val.decode('utf-8') if isinstance(sticker_val, bytes) else sticker_val
            debug_info = {'score': getattr(res.docs[0], 'score', 'N/A')}
    except Exception:
        logging.error(f"RediSearch system error for user {user_hash}")
        await get_messaging_provider().send_text(payload.user_id, "I experienced a system error while searching. Please try again later.")
        return # Gracefully abort on system failure, preventing false "no results" text
        
    if best_sticker_id:
        logging.info(f"Sending matched sticker to user {user_hash}.")
        await get_messaging_provider().send_sticker(payload.user_id, best_sticker_id)
        return {'sticker_id': best_sticker_id, 'debug': debug_info}
    else:
        logging.info(f"No matching sticker found. Sending text fallback to user {user_hash}.")
        await get_messaging_provider().send_text(payload.user_id, "Sorry, I couldn't find a matching sticker for your query.")
