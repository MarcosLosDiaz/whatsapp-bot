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
    if not body:
        return
    try:
        payload = json.loads(body)
        if not payload:
            return
        ingestion_worker.process_sticker(payload)
    except Exception as e:
        logging.exception(f"Error processing sticker msg: {e}")
        raise

@app.queue_trigger(arg_name="msg", queue_name="incoming-queries", connection="AzureWebJobsStorage")
def process_incoming_query(msg: func.QueueMessage) -> None:
    body = msg.get_body().decode('utf-8')
    if not body:
        return
    try:
        payload = json.loads(body)
        if not payload:
            return
        query_handler.handle_query(payload)
    except Exception as e:
        logging.exception(f"Error processing query msg: {e}")
        raise
