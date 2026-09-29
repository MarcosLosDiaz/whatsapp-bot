import azure.functions as func
from azure.monitor.opentelemetry import configure_azure_monitor
import json
import logging

# Set up telemetry
try:
    configure_azure_monitor()
except Exception as e:
    logging.warning(f"Failed to configure Azure Monitor: {e}")

from src import webhook_receiver, ingestion_worker, query_handler

app = func.FunctionApp()

@app.route(route="webhook", auth_level=func.AuthLevel.ANONYMOUS)
def webhook(req: func.HttpRequest) -> func.HttpResponse:
    # Need mock outputs since we aren't fully wiring out bindings here for simplicity in MVP.
    # In a real setup, we'd use multiple output bindings or QueueClients.
    # Using QueueClient directly is often easier in Python v2.
    # For now, let's just do a passthrough and log warning about missing bindings.
    
    class MockOut:
        def __init__(self):
            self.val = None
        def set(self, val):
            self.val = val
            
    stickers = MockOut()
    queries = MockOut()
    
    resp = webhook_receiver.main(req, stickers, queries)
    
    # In a real app with QueueClients
    if stickers.val:
        logging.info("Would queue sticker: " + str(stickers.val))
    if queries.val:
        logging.info("Would queue query: " + str(queries.val))
        
    return resp

@app.queue_trigger(arg_name="msg", queue_name="incoming-stickers", connection="AzureWebJobsStorage")
def process_incoming_sticker(msg: func.QueueMessage) -> None:
    body = msg.get_body().decode('utf-8')
    try:
        payload = json.loads(body)
        # Simplified parsing for the worker
        user_id = payload['entry'][0]['changes'][0]['value']['messages'][0]['from']
        sticker_id = payload['entry'][0]['changes'][0]['value']['messages'][0]['sticker']['id']
        media_id = sticker_id # In Meta, the media ID is usually the sticker ID.
        
        ingestion_worker.process_sticker({
            "user_id": user_id,
            "sticker_id": sticker_id,
            "media_id": media_id
        })
    except Exception as e:
        logging.error(f"Error processing sticker msg: {e}")

@app.queue_trigger(arg_name="msg", queue_name="incoming-queries", connection="AzureWebJobsStorage")
def process_incoming_query(msg: func.QueueMessage) -> None:
    body = msg.get_body().decode('utf-8')
    try:
        payload = json.loads(body)
        user_id = payload['entry'][0]['changes'][0]['value']['messages'][0]['from']
        
        # Meta text messages have 'text' object with 'body'
        query = "test query"
        try:
            query = payload['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
        except:
            pass
            
        query_handler.handle_query({
            "user_id": user_id,
            "query": query
        })
    except Exception as e:
        logging.error(f"Error processing query msg: {e}")
