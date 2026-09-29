import os
import logging
import requests
import struct
import base64
from openai import OpenAI
from azure.cosmos import CosmosClient
import redis
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# Global connection pooling
OPENAI_CLIENT = None
COSMOS_CONTAINER = None
REDIS_CLIENT = None

def get_openai_client():
    global OPENAI_CLIENT
    if not OPENAI_CLIENT:
        OPENAI_CLIENT = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
    return OPENAI_CLIENT

def get_cosmos_container():
    global COSMOS_CONTAINER
    if not COSMOS_CONTAINER:
        client = CosmosClient(os.environ['COSMOS_DB_URL'], credential=os.environ['COSMOS_DB_KEY'])
        COSMOS_CONTAINER = client.get_database_client('WhatsAppBot').get_container_client('stickers')
    return COSMOS_CONTAINER

def get_redis_client():
    global REDIS_CLIENT
    if not REDIS_CLIENT:
        REDIS_CLIENT = redis.Redis.from_url(f"redis://{os.environ['REDIS_HOST']}:{os.environ['REDIS_PORT']}")
    return REDIS_CLIENT

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type(requests.exceptions.ConnectionError))
def download_media(media_id: str, token: str) -> bytes:
    headers = {"Authorization": f"Bearer {token}"}
    url_resp = requests.get(f"https://graph.facebook.com/v18.0/{media_id}", headers=headers)
    url_resp.raise_for_status()
    media_url = url_resp.json().get('url')
    
    media_resp = requests.get(media_url, headers=headers)
    media_resp.raise_for_status()
    return media_resp.content

def process_sticker(payload: dict):
    user_id = payload['user_id']
    sticker_id = payload['sticker_id']
    media_id = payload['media_id']
    
    token = os.environ.get('META_GRAPH_TOKEN')
    if not token:
        raise ValueError("META_GRAPH_TOKEN is not set")
        
    media_bytes = download_media(media_id, token)
    b64_image = base64.b64encode(media_bytes).decode('utf-8')
    
    client = get_openai_client()
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this meme sticker."},
                {"type": "image_url", "image_url": {"url": f"data:image/webp;base64,{b64_image}"}}
            ]
        }]
    )
    description = response.choices[0].message.content
    
    embed_response = client.embeddings.create(
        model="text-embedding-3-small",
        input=description
    )
    embedding = embed_response.data[0].embedding
    
    container = get_cosmos_container()
    doc = {
        "id": sticker_id,
        "userId": user_id,
        "description": description,
        "embedding": embedding
    }
    container.upsert_item(doc)
    
    # Pack embedding to bytes for RediSearch (1536 floats)
    packed_embedding = struct.pack(f'{len(embedding)}f', *embedding)
    
    redis_client = get_redis_client()
    redis_client.hset(f"vector:{user_id}:{sticker_id}", mapping={
        b"vector": packed_embedding,
        b"stickerId": sticker_id.encode('utf-8')
    })
    redis_client.delete(f"user_history:{user_id}")
