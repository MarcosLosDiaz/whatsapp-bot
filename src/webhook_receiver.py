import logging
import json
import hmac
import hashlib
import azure.functions as func
from src.clients import get_queue_client
from src.schemas import MetaWebhookPayload, StickerQueuePayload, QueryQueuePayload
from src.config import config

def verify_signature(payload: bytes, signature_header: str, app_secret: str) -> bool:
    if not signature_header or not signature_header.startswith('sha256='):
        return False
    signature = signature_header.split('sha256=')[1]
    expected_signature = hmac.new(
        app_secret.encode('utf-8'),
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)

async def send_to_queue(queue_name: str, message: str):
    client = await get_queue_client(queue_name)
    await client.send_message(message)

async def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == 'GET':
        mode = req.params.get('hub.mode')
        token = req.params.get('hub.verify_token')
        challenge = req.params.get('hub.challenge')
            
        if mode == 'subscribe' and token and hmac.compare_digest(token, config.META_VERIFY_TOKEN):
            logging.info("Webhook verification succeeded")
            return func.HttpResponse(challenge, status_code=200)
        logging.warning("Webhook verification FAILED - invalid token or mode")
        return func.HttpResponse("Forbidden", status_code=403)
        
    elif req.method == 'POST':
        body_bytes = req.get_body()
        signature = req.headers.get('X-Hub-Signature-256', '')
        if not verify_signature(body_bytes, signature, config.META_APP_SECRET):
            logging.warning(f"Webhook signature verification FAILED. Content-Length={len(body_bytes)}")
            return func.HttpResponse("Forbidden", status_code=403)
        
        logging.info(f"Webhook POST received. Content-Length={len(body_bytes)}")
            
        try:
            req_body = req.get_json()
            payload = MetaWebhookPayload.model_validate(req_body)
        except Exception as e:
            logging.error(f"Invalid webhook payload: {type(e).__name__}: {e}. Routing to DLQ.")
            await send_to_queue("invalid-webhooks", body_bytes.decode('utf-8'))
            return func.HttpResponse("OK", status_code=200)
            
        sticker_count = 0
        query_count = 0
        for entry in payload.entry:
            for change in entry.changes:
                if not change.value.messages:
                    continue
                for message in change.value.messages:
                    try:
                        if message.type == 'sticker' and message.sticker:
                            q_msg = StickerQueuePayload(
                                user_id=message.from_,
                                sticker_id=message.sticker.id,
                                media_id=message.sticker.id
                            )
                            await send_to_queue("incoming-stickers", q_msg.model_dump_json())
                            sticker_count += 1
                        elif message.type == 'text' and message.text:
                            q_msg = QueryQueuePayload(
                                user_id=message.from_,
                                query=message.text.body
                            )
                            await send_to_queue("incoming-queries", q_msg.model_dump_json())
                            query_count += 1
                        else:
                            logging.info(f"Ignoring message type={message.type} from user")
                    except Exception as e:
                        logging.error(f"Queue dispatch error for message type={message.type}: {type(e).__name__}: {e}")
        
        logging.info(f"Webhook processed: {sticker_count} stickers, {query_count} queries queued")
        return func.HttpResponse("OK", status_code=200)

    return func.HttpResponse("Method Not Allowed", status_code=405)
