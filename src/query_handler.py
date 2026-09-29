import os
import logging
import struct
import asyncio
import aiohttp
from openai import AsyncOpenAI
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from src.redis_client import get_redis_client, ensure_index

OPENAI_CLIENT = None

def get_openai_client():
    global OPENAI_CLIENT
    if not OPENAI_CLIENT:
        OPENAI_CLIENT = AsyncOpenAI(api_key=os.environ['OPENAI_API_KEY'])
    return OPENAI_CLIENT

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type(aiohttp.ClientError))
async def send_sticker(user_id: str, sticker_id: str, token: str, phone_number_id: str):
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": user_id,
        "type": "sticker",
        "sticker": {
            "id": sticker_id
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            resp.raise_for_status()

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type(aiohttp.ClientError))
async def send_text_message(user_id: str, text: str, token: str, phone_number_id: str):
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": user_id,
        "type": "text",
        "text": {
            "body": text
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            resp.raise_for_status()

async def handle_query(payload: dict):
    user_id = payload['user_id']
    query = payload['query']
    
    await asyncio.to_thread(ensure_index)
    
    import re
    # Proper escaping for RediSearch TagFields: escape punctuation
    safe_user_id = re.sub(r'([+\-!@#$%^&*()_={}\[\]|\\:;"\'<>,.?/])', r'\\\1', user_id)
    
    phone_id = os.environ.get('META_PHONE_ID')
    token = os.environ.get('META_GRAPH_TOKEN')
    
    if not phone_id or not token:
        raise ValueError("Missing META_PHONE_ID or META_GRAPH_TOKEN")
        
    client = get_openai_client()
    embed_response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    )
    query_embedding = embed_response.data[0].embedding
    packed_embedding = struct.pack(f'<{len(query_embedding)}f', *query_embedding)
    
    redis_client = get_redis_client()
    
    best_sticker_id = None
    try:
        from redis.commands.search.query import Query
        q = Query(f'(@userId:{{{safe_user_id}}})=>[KNN 1 @vector $vec as score]').sort_by('score').return_fields('stickerId').dialect(2)
        res = await asyncio.to_thread(redis_client.ft('idx:stickers').search, q, query_params={'vec': packed_embedding})
        if res.docs:
            sticker_val = res.docs[0].stickerId
            best_sticker_id = sticker_val.decode('utf-8') if isinstance(sticker_val, bytes) else sticker_val
    except Exception as e:
        logging.warning(f"RediSearch failed or index not created: {e}")
        
    if best_sticker_id:
        await send_sticker(user_id, best_sticker_id, token, phone_id)
    else:
        await send_text_message(user_id, "Sorry, I couldn't find a matching sticker for your query.", token, phone_id)
