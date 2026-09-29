import logging
import struct
import base64
import uuid
import aiohttp
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from openai import APIConnectionError, RateLimitError, BadRequestError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from src.redis_client import ensure_index
from src.clients import get_aiohttp_session, get_openai_client, get_cosmos_stickers_container, get_cosmos_user_stickers_container, get_redis_client
from src.schemas import StickerQueuePayload, StickerDocument, UserStickerDocument
from src.config import config

class DistributedLockError(Exception):
    pass

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

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type((APIConnectionError, RateLimitError)))
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

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type((APIConnectionError, RateLimitError)))
async def generate_embeddings(description: str) -> list:
    client = await get_openai_client()
    embed_response = await client.embeddings.create(
        model=config.OPENAI_EMBEDDING_MODEL,
        input=description
    )
    return embed_response.data[0].embedding

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type(Exception))
async def save_to_cosmos(doc: StickerDocument):
    container = await get_cosmos_stickers_container()
    await container.upsert_item(doc.model_dump(by_alias=True, exclude_none=True))

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type(Exception))
async def save_user_sticker_mapping(user_id: str, sticker_id: str):
    container = await get_cosmos_user_stickers_container()
    doc = UserStickerDocument(id=f"{user_id}_{sticker_id}", userId=user_id, stickerId=sticker_id)
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

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type(aiohttp.ClientError))
async def send_text_message(user_id: str, text: str):
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": user_id,
        "type": "text",
        "text": {"body": text}
    }
    url = f"https://graph.facebook.com/{config.META_GRAPH_VERSION}/{config.META_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {config.META_GRAPH_TOKEN}", "Content-Type": "application/json"}
    session = await get_aiohttp_session()
    async with session.post(url, headers=headers, json=payload) as resp:
        resp.raise_for_status()

async def process_sticker(payload_dict: dict):
    payload = StickerQueuePayload.model_validate(payload_dict)
    
    await ensure_index()
    redis_client = await get_redis_client()
    
    if await redis_client.exists(f"vector:{payload.user_id}:{payload.sticker_id}"):
        return
        
    lock_key = f"lock:ingest:{payload.user_id}:{payload.sticker_id}"
    lock_val = str(uuid.uuid4())
    if not await redis_client.set(lock_key, lock_val, nx=True, ex=300):
        raise DistributedLockError("Lock held, preserving queue visibility")
    
    try:
        container = await get_cosmos_stickers_container()
        try:
            existing = await container.read_item(item=payload.sticker_id, partition_key=payload.sticker_id)
            doc = StickerDocument.model_validate(existing)
        except CosmosResourceNotFoundError:
            doc = StickerDocument(id=payload.sticker_id)

        try:
            if not doc.description:
                try:
                    media_bytes = await download_media(payload.media_id, config.META_GRAPH_TOKEN)
                except ValueError as e:
                    return # Drop non-image payloads permanently
                b64_image = base64.b64encode(media_bytes).decode('utf-8')
                doc.description = await generate_description(b64_image)
                if not doc.description:
                    raise ValueError("VLM returned empty description.")
                await save_to_cosmos(doc)
                
            if not doc.embedding:
                doc.embedding = await generate_embeddings(doc.description)
                await save_to_cosmos(doc)
                
        except BadRequestError as e:
            await send_text_message(payload.user_id, "I couldn't process your sticker due to a policy restriction.")
            return
            
        await save_user_sticker_mapping(payload.user_id, payload.sticker_id)
        
        packed_embedding = struct.pack(f'<{len(doc.embedding)}f', *doc.embedding)
        await save_to_redis(payload.user_id, payload.sticker_id, packed_embedding)
    finally:
        script = """
        if redis.call("get",KEYS[1]) == ARGV[1]
        then
            return redis.call("del",KEYS[1])
        else
            return 0
        end
        """
        await redis_client.eval(script, 1, lock_key, lock_val)
