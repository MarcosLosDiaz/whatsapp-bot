from src.messaging import get_messaging_provider
import logging
import struct
import base64
import uuid
import hashlib
import re
import aiohttp
from azure.cosmos.exceptions import CosmosResourceNotFoundError, CosmosResourceExistsError
from openai import APIConnectionError, RateLimitError, BadRequestError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from src.clients import get_aiohttp_session, get_openai_client, get_cosmos_stickers_container, get_cosmos_user_stickers_container
from src.schemas import StickerQueuePayload, StickerDocument, UserStickerDocument
from src.config import config

class DistributedLockError(Exception):
    pass

def hash_pii(data: str) -> str:
    return hashlib.sha256((data + config.PII_SALT).encode('utf-8')).hexdigest()[:8]



@retry(wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(10), retry=retry_if_exception_type((APIConnectionError, RateLimitError)))
async def generate_embeddings(description: str) -> list:
    client = await get_openai_client()
    embed_response = await client.embeddings.create(
        model=config.OPENAI_EMBEDDING_MODEL,
        input=description
    )
    return embed_response.data[0].embedding

@retry(wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(10), retry=retry_if_exception_type(Exception))
async def ensure_cosmos_skeleton(sticker_id: str):
    container = await get_cosmos_stickers_container()
    doc = StickerDocument(id=sticker_id)
    try:
        await container.create_item(doc.model_dump(by_alias=True, exclude_none=True))
    except CosmosResourceExistsError:
        pass

@retry(wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(10), retry=retry_if_exception_type(Exception))
async def conditional_patch_cosmos_field(sticker_id: str, field_path: str, value):
    from azure.cosmos.exceptions import CosmosHttpResponseError
    container = await get_cosmos_stickers_container()
    try:
        await container.patch_item(
            item=sticker_id,
            partition_key=sticker_id,
            patch_operations=[{"op": "set", "path": field_path, "value": value}],
            filter_predicate=f"FROM c WHERE NOT IS_DEFINED(c.{field_path.strip('/')})"
        )
    except CosmosHttpResponseError as e:
        if e.status_code == 412:
            return
        raise
async def save_user_sticker_mapping(user_id: str, sticker_id: str):
    container = await get_cosmos_user_stickers_container()
    hashed = hash_pii(user_id)
    doc = UserStickerDocument(id=f"{hashed}_{sticker_id}", userId=hashed, stickerId=sticker_id)
    await container.upsert_item(doc.model_dump(by_alias=True))

@retry(wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(10), retry=retry_if_exception_type(Exception))

@retry(wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(10), retry=retry_if_exception_type(Exception))

@retry(wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(10), retry=retry_if_exception_type(aiohttp.ClientError))

@retry(wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(10), retry=retry_if_exception_type(aiohttp.ClientError))
async def download_media(media_id: str, token: str) -> bytes:
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as session:
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

async def process_sticker(payload_dict: dict):
    payload = StickerQueuePayload.model_validate(payload_dict)
    user_hash = hash_pii(payload.user_id)
    logging.info(f"Processing sticker {payload.sticker_id} for user {user_hash}")
    
    try:
        await ensure_cosmos_skeleton(payload.sticker_id)
        
        container = await get_cosmos_stickers_container()
        existing = await container.read_item(item=payload.sticker_id, partition_key=payload.sticker_id)
        doc = StickerDocument.model_validate(existing)

        if doc.description == "[REJECTED]":
            await get_messaging_provider().send_text(payload.user_id, "I couldn't process your sticker due to a policy restriction.")
            
            return

        try:
            if not doc.description:
                try:
                    media_bytes = await download_media(payload.media_id, config.META_GRAPH_TOKEN)
                except ValueError:
                    return # Drop non-image payloads permanently
                except aiohttp.ClientError:
                    raise Exception("Network connection failed") from None # Force native queue retry
                
                b64_image = base64.b64encode(media_bytes).decode('utf-8')
                
                # Upload to Azure Blob Storage and store pointer in Cosmos DB
                from azure.storage.blob.aio import BlobServiceClient
                import os
                try:
                    async with BlobServiceClient.from_connection_string(os.environ.get("AzureWebJobsStorage", "UseDevelopmentStorage=true")) as blob_service_client:
                        container_client = blob_service_client.get_container_client("stickers")
                        try:
                            await container_client.create_container(public_access="blob")
                        except Exception:
                            pass
                        
                        blob_client = container_client.get_blob_client(f"{payload.sticker_id}.webp")
                        await blob_client.upload_blob(media_bytes, overwrite=True)
                        doc.blob_url = blob_client.url
                        await conditional_patch_cosmos_field(payload.sticker_id, "/blob_url", blob_client.url)
                except Exception as e:
                    logging.warning(f"Failed to upload {payload.sticker_id} to blob storage: {e}")
                
                from src.agent import run_vision_agent
                description = await run_vision_agent(b64_image)

                if not description:
                    return # VLM semantic permanent failure drop
                
                doc.description = description
                # Conditional Patch prevents full document contention and "Last Write Wins" race conditions
                await conditional_patch_cosmos_field(payload.sticker_id, "/description", description)
                
            if not doc.embedding:
                doc.embedding = await generate_embeddings(doc.description)
                await conditional_patch_cosmos_field(payload.sticker_id, "/embedding", doc.embedding)
                
        except BadRequestError:
            logging.error(f"Semantic API failure on sticker {payload.sticker_id}")
            doc.description = "[REJECTED]"
            await conditional_patch_cosmos_field(payload.sticker_id, "/description", "[REJECTED]")
            await get_messaging_provider().send_text(payload.user_id, "I couldn't process your sticker due to a policy restriction.")
            
            return
            
        await save_user_sticker_mapping(payload.user_id, payload.sticker_id)
        

        await get_messaging_provider().send_text(payload.user_id, "Sticker saved successfully!")
    finally:
        pass
