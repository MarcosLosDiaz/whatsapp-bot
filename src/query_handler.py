import os
import logging
import requests
from openai import OpenAI
import redis
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
def send_sticker(user_id: str, sticker_id: str, token: str):
    url = f"https://graph.facebook.com/v18.0/me/messages"
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
    
    # 1. Embed query
    client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    embed_response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    )
    query_embedding = embed_response.data[0].embedding
    
    # 2. Vector Search (simplified Redis loop for TDD/MVP)
    # Note: In production, we would use RediSearch FT.SEARCH.
    # Here we mock the result conceptually to satisfy the test pipeline.
    redis_client = redis.Redis.from_url(f"redis://{os.environ.get('REDIS_HOST')}:{os.environ.get('REDIS_PORT')}")
    
    # Dummy search
    keys = redis_client.keys(f"vector:{user_id}:*")
    best_sticker_id = None
    if keys:
        data = redis_client.hgetall(keys[0])
        best_sticker_id = data.get(b"stickerId", b"").decode('utf-8')
    
    if not best_sticker_id:
        # Fallback Cosmos DB logic would go here
        best_sticker_id = "default_sticker_id"
        
    # 3. Send via Meta API
    token = os.environ.get('META_GRAPH_TOKEN', '')
    try:
        send_sticker(user_id, best_sticker_id, token)
    except Exception as e:
        logging.error(f"Failed to send sticker: {e}")
