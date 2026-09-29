import os
import struct
import base64
import aiohttp
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from src.redis_client import ensure_index
from src.clients import get_aiohttp_session, get_openai_client, get_cosmos_container, get_redis_client

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type(aiohttp.ClientError))
async def download_media(media_id: str, token: str) -> bytes:
    headers = {"Authorization": f"Bearer {token}"}
    session = await get_aiohttp_session()
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
    
    token = os.environ['META_GRAPH_TOKEN'] # Fail fast if missing
        
    media_bytes = await download_media(media_id, token)
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
