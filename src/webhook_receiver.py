import azure.functions as func
import logging
import os
import json

def main(req: func.HttpRequest, msg_stickers: func.Out, msg_queries: func.Out) -> func.HttpResponse:
    logging.info('Webhook triggered.')
    
    if req.method == 'GET':
        mode = req.params.get('hub.mode')
        token = req.params.get('hub.verify_token')
        challenge = req.params.get('hub.challenge')
        
        verify_token = os.environ.get('META_VERIFY_TOKEN')
        
        if mode == 'subscribe' and token == verify_token:
            return func.HttpResponse(challenge, status_code=200)
        return func.HttpResponse("Forbidden", status_code=403)
        
    elif req.method == 'POST':
        try:
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse("Invalid JSON", status_code=400)
            
        # Parse minimal info to determine queue
        try:
            entry = req_body.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            value = changes.get('value', {})
            message = value.get('messages', [{}])[0]
            msg_type = message.get('type')
            
            if msg_type == 'sticker':
                msg_stickers.set(json.dumps(req_body))
            elif msg_type == 'text':
                msg_queries.set(json.dumps(req_body))
                
            return func.HttpResponse("OK", status_code=200)
        except Exception as e:
            logging.error(f"Error parsing message: {e}")
            return func.HttpResponse("Error processing", status_code=500)

    return func.HttpResponse("Method Not Allowed", status_code=405)
