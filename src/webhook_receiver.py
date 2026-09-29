import logging
import os
import json
import hmac
import hashlib
import azure.functions as func
from src.clients import get_queue_client

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
        except ValueError:
            logging.error("Invalid JSON")
            return func.HttpResponse("OK", status_code=200)
            
        entries = req_body.get('entry', [])
        for entry in entries:
            changes = entry.get('changes', [])
            for change in changes:
                value = change.get('value', {})
                messages = value.get('messages', [])
                for message in messages:
                    msg_type = message.get('type')
                    user_id = message.get('from')
                    
                    if not user_id:
                        continue
                    
                    if msg_type == 'sticker':
                        sticker_id = message.get('sticker', {}).get('id')
                        if sticker_id:
                            try:
                                await send_to_queue("incoming-stickers", json.dumps({
                                    "user_id": user_id,
                                    "sticker_id": sticker_id,
                                    "media_id": sticker_id
                                }))
                            except Exception as e:
                                logging.error(f"Queue error: {e}")
                                return func.HttpResponse("Internal Server Error", status_code=500)
                    elif msg_type == 'text':
                        query = message.get('text', {}).get('body')
                        if query:
                            try:
                                await send_to_queue("incoming-queries", json.dumps({
                                    "user_id": user_id,
                                    "query": query
                                }))
                            except Exception as e:
                                logging.error(f"Queue error: {e}")
                                return func.HttpResponse("Internal Server Error", status_code=500)
        
        return func.HttpResponse("OK", status_code=200)

    return func.HttpResponse("Method Not Allowed", status_code=405)
