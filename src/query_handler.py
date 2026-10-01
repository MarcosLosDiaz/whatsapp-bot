from src.messaging import get_messaging_provider
import logging
import hashlib
import aiohttp
from openai import APIConnectionError, RateLimitError, BadRequestError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from src.clients import get_aiohttp_session, get_openai_client, get_cosmos_stickers_container
from src.schemas import QueryQueuePayload
from src.config import config

@retry(wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(10), retry=retry_if_exception_type((APIConnectionError, RateLimitError)))
async def get_query_embedding(query: str):
    client = await get_openai_client()
    embed_response = await client.embeddings.create(
        model=config.OPENAI_EMBEDDING_MODEL,
        input=query
    )
    return embed_response.data[0].embedding

def hash_pii(data: str) -> str:
    return hashlib.sha256((data + config.PII_SALT).encode('utf-8')).hexdigest()[:8]

async def handle_query(payload_dict: dict):
    payload = QueryQueuePayload.model_validate(payload_dict)
    
    user_hash = hash_pii(payload.user_id)
    logging.info(f"Handling query [REDACTED] for user {user_hash}")
    
    normalized_user = hash_pii(payload.user_id)
        
    try:
        query_embedding = await get_query_embedding(payload.query)
    except BadRequestError:
        logging.error(f"Semantic API failure on query for user {user_hash}")
        await get_messaging_provider().send_text(payload.user_id, "I couldn't process your query due to a policy restriction.")
        return
        
    container = await get_cosmos_stickers_container()
    
    best_sticker_id = None
    debug_info = None
    try:
        query = """
            SELECT TOP 1 c.id, VectorDistance(c.embedding, @embedding) AS score 
            FROM c 
            ORDER BY VectorDistance(c.embedding, @embedding)
        """
        parameters = [
            {"name": "@embedding", "value": query_embedding}
        ]
        
        results = container.query_items(
            query=query,
            parameters=parameters,
            
        )
        
        async for item in results:
            best_sticker_id = item['id']
            debug_info = {'score': item.get('score', 'N/A')}
            break
            
    except Exception as e:
        logging.error(f"Cosmos DB system error for user {user_hash}: {e}")
        await get_messaging_provider().send_text(payload.user_id, "I experienced a system error while searching. Please try again later.")
        return
        
    if best_sticker_id:
        logging.info(f"Sending matched sticker to user {user_hash}.")
        await get_messaging_provider().send_sticker(payload.user_id, best_sticker_id)
        return {'sticker_id': best_sticker_id, 'debug': debug_info}
    else:
        logging.info(f"No matching sticker found. Sending text fallback to user {user_hash}.")
        await get_messaging_provider().send_text(payload.user_id, "Sorry, I couldn't find a matching sticker for your query.")
