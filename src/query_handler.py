import os
import logging
import requests
import struct
from openai import OpenAI
import redis
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

OPENAI_CLIENT = None
REDIS_CLIENT = None

def get_openai_client():
    global OPENAI_CLIENT
    if not OPENAI_CLIENT:
        OPENAI_CLIENT = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
    return OPENAI_CLIENT

def get_redis_client():
    global REDIS_CLIENT
    if not REDIS_CLIENT:
        # Avoid decode_responses=True because we deal with raw vector bytes
        REDIS_CLIENT = redis.Redis.from_url(f"redis://{os.environ['REDIS_HOST']}:{os.environ['REDIS_PORT']}")
    return REDIS_CLIENT

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.HTTPError)))
def send_sticker(user_id: str, sticker_id: str, token: str, phone_number_id: str):
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
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()

def handle_query(payload: dict):
    user_id = payload['user_id']
    query = payload['query']
    
    # Strip '+' to avoid RediSearch syntax errors
    safe_user_id = user_id.replace('+', '')
    
    phone_id = os.environ.get('META_PHONE_ID')
    token = os.environ.get('META_GRAPH_TOKEN')
    
    if not phone_id or not token:
        raise ValueError("Missing META_PHONE_ID or META_GRAPH_TOKEN")
        
    client = get_openai_client()
    embed_response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    )
    query_embedding = embed_response.data[0].embedding
    packed_embedding = struct.pack(f'<{len(query_embedding)}f', *query_embedding)
    
    redis_client = get_redis_client()
    
    try:
        from redis.commands.search.query import Query
        q = Query(f'(@userId:{{{safe_user_id}}})=>[KNN 1 @vector $vec as score]').sort_by('score').return_fields('stickerId').dialect(2)
        res = redis_client.ft('idx:stickers').search(q, query_params={'vec': packed_embedding})
        if res.docs:
            sticker_val = res.docs[0].stickerId
            best_sticker_id = sticker_val.decode('utf-8') if isinstance(sticker_val, bytes) else sticker_val
        else:
            best_sticker_id = "default_sticker_id"
    except Exception as e:
        logging.warning(f"RediSearch failed or index not created: {e}")
        best_sticker_id = "default_sticker_id"
        
    send_sticker(user_id, best_sticker_id, token, phone_id)
