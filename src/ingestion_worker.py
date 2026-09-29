import struct
import base64
import aiohttp
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from openai import APIError, APIConnectionError, RateLimitError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from src.redis_client import ensure_index
from src.clients import get_aiohttp_session, get_openai_client, get_cosmos_container, get_redis_client
from src.schemas import StickerQueuePayload, StickerDocument
from src.config import config

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type(aiohttp.ClientError))
async def download_media(media_id: str, token: str) -> bytes:
    headers = {"Authorization": f"Bearer {token}"}
    session = await get_aiohttp_session()
    async with session.get(f"https://graph.facebook.com/{config.META_GRAPH_VERSION}/{media_id}", headers=headers) as url_resp:
        url_resp.raise_for_status()
        data = await url_resp.json()
        media_url = data.get('url')
    
    async with session.get(media_url, headers=headers) as media_resp:
        media_resp.raise_for_status()
        content_type = media_resp.headers.get('Content-Type', '')
        if not content_type.startswith('image/'):
            raise ValueError(f"Invalid media type: {content_type}")
        return await media_resp.read()

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type((APIError, APIConnectionError, RateLimitError)))
async def generate_description(b64_image: str) -> str:
    client = await get_openai_client()
    response = await client.chat.completions.create(
        model=config.OPENAI_VLM_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this meme sticker."},
                {"type": "image_url", "image_url": {"url": f"data:image/webp;base64,{b64_image}"}}
            ]
        }]
    )
    return response.choices[0].message.content

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type((APIError, APIConnectionError, RateLimitError)))
async def generate_embeddings(description: str) -> list:
    client = await get_openai_client()
    embed_response = await client.embeddings.create(
        model=config.OPENAI_EMBEDDING_MODEL,
        input=description
    )
    return embed_response.data[0].embedding

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type(Exception))
async def save_to_cosmos(doc: StickerDocument):
    container = await get_cosmos_container()
    await container.upsert_item(doc.model_dump(by_alias=True))

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type(Exception))
async def save_to_redis(user_id: str, sticker_id: str, packed_embedding: bytes):
    redis_client = await get_redis_client()
    await redis_client.hset(f"vector:{user_id}:{sticker_id}", mapping={
        b"vector": packed_embedding,
        b"stickerId": sticker_id.encode('utf-8'),
        b"userId": user_id.encode('utf-8')
    })
    await redis_client.delete(f"user_history:{user_id}")

async def process_sticker(payload_dict: dict):
    payload = StickerQueuePayload.model_validate(payload_dict)
    
    await ensure_index()
    
    redis_client = await get_redis_client()
    
    # Fast idempotent check
    if await redis_client.exists(f"vector:{payload.user_id}:{payload.sticker_id}"):
        return
        
    # Distributed lock to prevent race conditions on duplicate queue events
    lock_key = f"lock:ingest:{payload.user_id}:{payload.sticker_id}"
    if not await redis_client.set(lock_key, "1", nx=True, ex=300):
        return # Another worker is actively processing this exact sticker
    
    try:
        # Check if Cosmos already has it (Partial failure recovery to prevent VLM cost bleed)
        container = await get_cosmos_container()
        try:
            existing = await container.read_item(item=payload.sticker_id, partition_key=payload.user_id)
            doc = StickerDocument.model_validate(existing)
            embedding = doc.embedding
        except CosmosResourceNotFoundError:
            # Need to run VLM pipeline
            media_bytes = await download_media(payload.media_id, config.META_GRAPH_TOKEN)
            b64_image = base64.b64encode(media_bytes).decode('utf-8')
            
            description = await generate_description(b64_image)
            if not description:
                raise ValueError("VLM failed to generate a description for the sticker.")
            
            embedding = await generate_embeddings(description)
            
            doc = StickerDocument(
                id=payload.sticker_id,
                userId=payload.user_id,
                description=description,
                embedding=embedding
            )
            await save_to_cosmos(doc)
        
        packed_embedding = struct.pack(f'<{len(embedding)}f', *embedding)
        await save_to_redis(payload.user_id, payload.sticker_id, packed_embedding)
    finally:
        await redis_client.delete(lock_key)
