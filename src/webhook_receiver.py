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

def main(req: func.HttpRequest, msg_stickers: func.Out, msg_queries: func.Out) -> func.HttpResponse:
    if req.method == 'GET':
        mode = req.params.get('hub.mode')
        token = req.params.get('hub.verify_token')
        challenge = req.params.get('hub.challenge')
        
        verify_token = os.environ.get('META_VERIFY_TOKEN', '')
        
        # Use compare_digest to prevent timing attacks
        if mode == 'subscribe' and token and hmac.compare_digest(token, verify_token):
            return func.HttpResponse(challenge, status_code=200)
        return func.HttpResponse("Forbidden", status_code=403)
        
    elif req.method == 'POST':
        # 1. Verify Signature
        app_secret = os.environ.get('META_APP_SECRET', '')
        signature = req.headers.get('X-Hub-Signature-256', '')
        if app_secret and not verify_signature(req.get_body(), signature, app_secret):
            logging.warning("Invalid webhook signature")
            return func.HttpResponse("Forbidden", status_code=403)
            
        try:
            req_body = req.get_json()
        except ValueError:
            logging.error("Invalid JSON received")
            # Return 200 to prevent Meta from retrying malformed payloads
            return func.HttpResponse("OK", status_code=200)
            
        # Parse minimal info safely without IndexError traps
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
            
        # Always return 200 OK so Meta doesn't retry
        return func.HttpResponse("OK", status_code=200)

    return func.HttpResponse("Method Not Allowed", status_code=405)
