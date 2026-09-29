import logging
import os
import json
import hmac
import hashlib
import azure.functions as func
from src.clients import get_queue_client
from src.schemas import MetaWebhookPayload, StickerQueuePayload, QueryQueuePayload

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
    # Eagerly load secrets during request processing to avoid module-level crash
    try:
        verify_token = os.environ['META_VERIFY_TOKEN']
        app_secret = os.environ['META_APP_SECRET']
    except KeyError as e:
        logging.error(f"Missing configuration: {e}")
        return func.HttpResponse("Internal Server Error", status_code=500)

    if req.method == 'GET':
        mode = req.params.get('hub.mode')
        token = req.params.get('hub.verify_token')
        challenge = req.params.get('hub.challenge')
            
        if mode == 'subscribe' and token and hmac.compare_digest(token, verify_token):
            return func.HttpResponse(challenge, status_code=200)
        return func.HttpResponse("Forbidden", status_code=403)
        
    elif req.method == 'POST':
        signature = req.headers.get('X-Hub-Signature-256', '')
        if not verify_signature(req.get_body(), signature, app_secret):
            return func.HttpResponse("Forbidden", status_code=403)
            
        try:
            req_body = req.get_json()
            payload = MetaWebhookPayload.model_validate(req_body)
        except Exception as e:
            logging.error(f"Invalid Payload: {e}")
            return func.HttpResponse("OK", status_code=200) # Stop Meta from retrying bad schemas
            
        for entry in payload.entry:
            for change in entry.changes:
                if not change.value.messages:
                    continue
                for message in change.value.messages:
                    if message.type == 'sticker' and message.sticker:
                        try:
                            q_msg = StickerQueuePayload(
                                user_id=message.from_,
                                sticker_id=message.sticker.id,
                                media_id=message.sticker.id
                            )
                            await send_to_queue("incoming-stickers", q_msg.model_dump_json())
                        except Exception as e:
                            logging.error(f"Queue error: {e}")
                            return func.HttpResponse("Internal Server Error", status_code=500)
                    elif message.type == 'text' and message.text:
                        try:
                            q_msg = QueryQueuePayload(
                                user_id=message.from_,
                                query=message.text.body
                            )
                            await send_to_queue("incoming-queries", q_msg.model_dump_json())
                        except Exception as e:
                            logging.error(f"Queue error: {e}")
                            return func.HttpResponse("Internal Server Error", status_code=500)
        
        return func.HttpResponse("OK", status_code=200)

    return func.HttpResponse("Method Not Allowed", status_code=405)
