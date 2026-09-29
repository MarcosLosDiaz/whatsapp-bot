import azure.functions as func
import logging
import os
import json
import hmac
import hashlib

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

def main(req: func.HttpRequest, msg_stickers: func.Out[str], msg_queries: func.Out[str]) -> func.HttpResponse:
    if req.method == 'GET':
        mode = req.params.get('hub.mode')
        token = req.params.get('hub.verify_token')
        challenge = req.params.get('hub.challenge')
        
        verify_token = os.environ.get('META_VERIFY_TOKEN')
        if not verify_token:
            logging.error("META_VERIFY_TOKEN is not set.")
            return func.HttpResponse("Internal Server Error", status_code=500)
            
        if mode == 'subscribe' and token and hmac.compare_digest(token, verify_token):
            return func.HttpResponse(challenge, status_code=200)
        return func.HttpResponse("Forbidden", status_code=403)
        
    elif req.method == 'POST':
        app_secret = os.environ.get('META_APP_SECRET')
        if not app_secret:
            logging.error("META_APP_SECRET is not set.")
            return func.HttpResponse("Internal Server Error", status_code=500)
            
        signature = req.headers.get('X-Hub-Signature-256', '')
        if not verify_signature(req.get_body(), signature, app_secret):
            logging.warning("Invalid webhook signature")
            return func.HttpResponse("Forbidden", status_code=403)
            
        try:
            req_body = req.get_json()
        except ValueError:
            logging.error("Invalid JSON received")
            return func.HttpResponse("OK", status_code=200)
            
        try:
            entries = req_body.get('entry', [])
            if not entries:
                return func.HttpResponse("OK", status_code=200)
                
            changes = entries[0].get('changes', [])
            if not changes:
                return func.HttpResponse("OK", status_code=200)
                
            value = changes[0].get('value', {})
            messages = value.get('messages', [])
            if not messages:
                return func.HttpResponse("OK", status_code=200)
                
            message = messages[0]
            msg_type = message.get('type')
            
            if msg_type == 'sticker':
                msg_stickers.set(json.dumps(req_body))
            elif msg_type == 'text':
                msg_queries.set(json.dumps(req_body))
                
        except Exception:
            logging.exception("Unexpected error parsing message")
            
        return func.HttpResponse("OK", status_code=200)

    return func.HttpResponse("Method Not Allowed", status_code=405)
