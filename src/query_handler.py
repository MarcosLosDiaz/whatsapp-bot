import logging
import struct
import aiohttp
from openai import APIConnectionError, RateLimitError, BadRequestError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from src.redis_client import ensure_index
from src.clients import get_aiohttp_session, get_openai_client, get_redis_client
from src.schemas import QueryQueuePayload
from src.config import config

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type(aiohttp.ClientError))
async def send_message_payload(payload: dict):
    url = f"https://graph.facebook.com/{config.META_GRAPH_VERSION}/{config.META_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {config.META_GRAPH_TOKEN}", "Content-Type": "application/json"}
    session = await get_aiohttp_session()
    async with session.post(url, headers=headers, json=payload) as resp:
        resp.raise_for_status()

async def send_sticker(user_id: str, sticker_id: str):
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": user_id,
        "type": "sticker",
        "sticker": {"id": sticker_id}
    }
    await send_message_payload(payload)

async def send_text_message(user_id: str, text: str):
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": user_id,
        "type": "text",
        "text": {"body": text}
    }
    await send_message_payload(payload)

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type((APIConnectionError, RateLimitError)))
async def get_query_embedding(query: str):
    client = await get_openai_client()
    embed_response = await client.embeddings.create(
        model=config.OPENAI_EMBEDDING_MODEL,
        input=query
    )
    return embed_response.data[0].embedding

async def handle_query(payload_dict: dict):
    payload = QueryQueuePayload.model_validate(payload_dict)
    logging.info(f"Handling query '{payload.query}' for user {payload.user_id}")
    
    await ensure_index()
    
    import re
    safe_user_id = re.sub(r'([+\-!@#$%^&*()_={}\[\]|\\:;"\'<>,.?/])', r'\\\1', payload.user_id)
        
    try:
        query_embedding = await get_query_embedding(payload.query)
    except BadRequestError as e:
        logging.error(f"Semantic API failure on query: {e}")
        await send_text_message(payload.user_id, "I couldn't process your query due to a policy restriction.")
        return # Drop permanent failure
        
    packed_embedding = struct.pack(f'<{len(query_embedding)}f', *query_embedding)
    
    redis_client = await get_redis_client()
    
    best_sticker_id = None
    try:
        from redis.commands.search.query import Query
        q = Query(f'(@userId:{{{safe_user_id}}})=>[KNN 1 @vector $vec as score]').sort_by('score').return_fields('stickerId').dialect(2)
        res = await redis_client.ft('idx:stickers').search(q, query_params={'vec': packed_embedding})
        if res.docs:
            sticker_val = res.docs[0].stickerId
            best_sticker_id = sticker_val.decode('utf-8') if isinstance(sticker_val, bytes) else sticker_val
    except Exception as e:
        logging.warning(f"RediSearch failed or index not created: {e}")
        
    if best_sticker_id:
        logging.info(f"Sending matched sticker {best_sticker_id} to user.")
        await send_sticker(payload.user_id, best_sticker_id)
    else:
        logging.info("No matching sticker found. Sending text fallback.")
        await send_text_message(payload.user_id, "Sorry, I couldn't find a matching sticker for your query.")
