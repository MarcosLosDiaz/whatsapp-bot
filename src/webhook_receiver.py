import logging
import os
import json
import hmac
import hashlib
import azure.functions as func
from azure.storage.queue.aio import QueueClient
from azure.storage.queue import TextBase64EncodePolicy

META_VERIFY_TOKEN = os.environ['META_VERIFY_TOKEN']
META_APP_SECRET = os.environ['META_APP_SECRET']
AZURE_WEBJOBS_STORAGE = os.environ.get('AzureWebJobsStorage')

QUEUE_CLIENTS = {}

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

def get_queue_client(queue_name: str):
    global QUEUE_CLIENTS
    if queue_name not in QUEUE_CLIENTS:
        if AZURE_WEBJOBS_STORAGE:
            QUEUE_CLIENTS[queue_name] = QueueClient.from_connection_string(
                AZURE_WEBJOBS_STORAGE, 
                queue_name,
                message_encode_policy=TextBase64EncodePolicy()
            )
    return QUEUE_CLIENTS.get(queue_name)

async def send_to_queue(queue_name: str, message: str):
    client = get_queue_client(queue_name)
    if client:
        await client.send_message(message)

async def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == 'GET':
        mode = req.params.get('hub.mode')
        token = req.params.get('hub.verify_token')
        challenge = req.params.get('hub.challenge')
            
        if mode == 'subscribe' and token and hmac.compare_digest(token, META_VERIFY_TOKEN):
            return func.HttpResponse(challenge, status_code=200)
        return func.HttpResponse("Forbidden", status_code=403)
        
    elif req.method == 'POST':
        signature = req.headers.get('X-Hub-Signature-256', '')
        if not verify_signature(req.get_body(), signature, META_APP_SECRET):
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
