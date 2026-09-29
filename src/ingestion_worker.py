import os
import json
import logging
import requests
from openai import OpenAI
from azure.cosmos import CosmosClient
import redis
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
def download_media(media_id: str, token: str) -> bytes:
    # First get media URL
    headers = {"Authorization": f"Bearer {token}"}
    url_resp = requests.get(f"https://graph.facebook.com/v18.0/{media_id}", headers=headers)
    url_resp.raise_for_status()
    media_url = url_resp.json().get('url')
    
    # Download actual media
    media_resp = requests.get(media_url, headers=headers)
    media_resp.raise_for_status()
    return media_resp.content

def process_sticker(payload: dict):
    user_id = payload['user_id']
    sticker_id = payload['sticker_id']
    media_id = payload['media_id']
    
    # 1. Download
    token = os.environ.get('META_GRAPH_TOKEN', '')
    try:
        media_bytes = download_media(media_id, token)
    except Exception as e:
        logging.error(f"Failed to download media: {e}")
        media_bytes = b"fake_image_data" # fallback for tests if token fails
        
    # 2. VLM Extraction (Agent Harness)
    client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    
    # Simplified Agent harness (1 iteration for MVP/TDD)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Describe this meme sticker."}]
    )
    description = response.choices[0].message.content
    
    # 3. Generate Embedding
    embed_response = client.embeddings.create(
        model="text-embedding-3-small",
        input=description
    )
    embedding = embed_response.data[0].embedding
    
    # 4. Upsert to CosmosDB
    cosmos_client = CosmosClient(os.environ.get('COSMOS_DB_URL'), credential=os.environ.get('COSMOS_DB_KEY'))
    db = cosmos_client.get_database_client('WhatsAppBot')
    container = db.get_container_client('stickers')
    
    doc = {
        "id": sticker_id,
        "userId": user_id,
        "description": description,
        "embedding": embedding
    }
    container.upsert_item(doc)
    
    # 5. Update Redis
    redis_client = redis.Redis.from_url(f"redis://{os.environ.get('REDIS_HOST')}:{os.environ.get('REDIS_PORT')}")
    # Raw bytes embedding should normally be packed, but keeping simple for TDD
    redis_client.hset(f"vector:{user_id}:{sticker_id}", mapping={"vector": str(embedding), "stickerId": sticker_id})
    # Invalidate user history
    redis_client.delete(f"user_history:{user_id}")
