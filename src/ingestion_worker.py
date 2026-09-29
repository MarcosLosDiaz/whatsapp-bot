import os
import logging
import struct
import base64
import aiohttp
from openai import AsyncOpenAI
from azure.cosmos.aio import CosmosClient
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from src.redis_client import get_redis_client, ensure_index

OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
COSMOS_DB_URL = os.environ['COSMOS_DB_URL']
COSMOS_DB_KEY = os.environ['COSMOS_DB_KEY']
META_GRAPH_TOKEN = os.environ['META_GRAPH_TOKEN']

OPENAI_CLIENT = None
COSMOS_CONTAINER = None
AIOHTTP_SESSION = None

def get_openai_client():
    global OPENAI_CLIENT
    if not OPENAI_CLIENT:
        OPENAI_CLIENT = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return OPENAI_CLIENT

async def get_cosmos_container():
    global COSMOS_CONTAINER
    if not COSMOS_CONTAINER:
        client = CosmosClient(COSMOS_DB_URL, credential=COSMOS_DB_KEY)
        db = client.get_database_client('WhatsAppBot')
        COSMOS_CONTAINER = db.get_container_client('stickers')
    return COSMOS_CONTAINER

def get_aiohttp_session():
    global AIOHTTP_SESSION
    if AIOHTTP_SESSION is None:
        AIOHTTP_SESSION = aiohttp.ClientSession()
    return AIOHTTP_SESSION

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type(aiohttp.ClientError))
async def download_media(media_id: str, token: str) -> bytes:
    headers = {"Authorization": f"Bearer {token}"}
    session = get_aiohttp_session()
    async with session.get(f"https://graph.facebook.com/v18.0/{media_id}", headers=headers) as url_resp:
        url_resp.raise_for_status()
        data = await url_resp.json()
        media_url = data.get('url')
    
    async with session.get(media_url, headers=headers) as media_resp:
        media_resp.raise_for_status()
        content_type = media_resp.headers.get('Content-Type', '')
        if not content_type.startswith('image/'):
            raise ValueError(f"Invalid media type: {content_type}")
        return await media_resp.read()

async def process_sticker(payload: dict):
    user_id = payload['user_id']
    sticker_id = payload['sticker_id']
    media_id = payload['media_id']
    
    await ensure_index()
        
    media_bytes = await download_media(media_id, META_GRAPH_TOKEN)
    b64_image = base64.b64encode(media_bytes).decode('utf-8')
    
    client = get_openai_client()
    
    response = await client.chat.completions.create(
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
    if not description:
        raise ValueError("VLM failed to generate a description for the sticker.")
    
    embed_response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=description
    )
    embedding = embed_response.data[0].embedding
    
    container = await get_cosmos_container()
    doc = {
        "id": sticker_id,
        "userId": user_id,
        "description": description,
        "embedding": embedding
    }
    await container.upsert_item(doc)
    
    packed_embedding = struct.pack(f'<{len(embedding)}f', *embedding)
    
    redis_client = get_redis_client()
    await redis_client.hset(f"vector:{user_id}:{sticker_id}", mapping={
        b"vector": packed_embedding,
        b"stickerId": sticker_id.encode('utf-8'),
        b"userId": user_id.encode('utf-8')
    })
    await redis_client.delete(f"user_history:{user_id}")
