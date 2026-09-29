import azure.functions as func
from azure.monitor.opentelemetry import configure_azure_monitor
import json
import logging

try:
    configure_azure_monitor()
except Exception as e:
    logging.warning(f"Failed to configure Azure Monitor: {e}")

from src import webhook_receiver, ingestion_worker, query_handler

app = func.FunctionApp()

@app.route(route="webhook", auth_level=func.AuthLevel.ANONYMOUS)
@app.queue_output(arg_name="msg_stickers", queue_name="incoming-stickers", connection="AzureWebJobsStorage")
@app.queue_output(arg_name="msg_queries", queue_name="incoming-queries", connection="AzureWebJobsStorage")
def webhook(req: func.HttpRequest, msg_stickers: func.Out[str], msg_queries: func.Out[str]) -> func.HttpResponse:
    return webhook_receiver.main(req, msg_stickers, msg_queries)

@app.queue_trigger(arg_name="msg", queue_name="incoming-stickers", connection="AzureWebJobsStorage")
def process_incoming_sticker(msg: func.QueueMessage) -> None:
    body = msg.get_body().decode('utf-8')
    try:
        payload = json.loads(body)
        messages = payload.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {}).get('messages', [])
        if not messages:
            logging.warning("No messages found in sticker payload.")
            return
            
        message = messages[0]
        user_id = message.get('from')
        sticker_id = message.get('sticker', {}).get('id')
        
        if not user_id or not sticker_id:
            logging.warning("Missing user_id or sticker_id in payload.")
            return
            
        ingestion_worker.process_sticker({
            "user_id": user_id,
            "sticker_id": sticker_id,
            "media_id": sticker_id
        })
    except Exception as e:
        logging.exception(f"Error processing sticker msg: {e}")
        raise # Re-raise to DLQ

@app.queue_trigger(arg_name="msg", queue_name="incoming-queries", connection="AzureWebJobsStorage")
def process_incoming_query(msg: func.QueueMessage) -> None:
    body = msg.get_body().decode('utf-8')
    try:
        payload = json.loads(body)
        messages = payload.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {}).get('messages', [])
        if not messages:
            logging.warning("No messages found in query payload.")
            return
            
        message = messages[0]
        user_id = message.get('from')
        query = message.get('text', {}).get('body')
        
        if not user_id or not query:
            logging.warning("Missing user_id or query text in payload.")
            return
            
        query_handler.handle_query({
            "user_id": user_id,
            "query": query
        })
    except Exception as e:
        logging.exception(f"Error processing query msg: {e}")
        raise # Re-raise to DLQ
