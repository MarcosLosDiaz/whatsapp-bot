import azure.functions as func
from azure.monitor.opentelemetry import configure_azure_monitor
import json
import logging
import os

try:
    if os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING'):
        configure_azure_monitor()
    else:
        logging.warning("APPLICATIONINSIGHTS_CONNECTION_STRING is missing. Telemetry is disabled.")
except Exception as e:
    logging.warning(f"Failed to configure Azure Monitor: {type(e).__name__}")

from src import webhook_receiver, ingestion_worker, query_handler
from src.ingestion_worker import DistributedLockError
from src.clients import get_queue_client

app = func.FunctionApp()

async def nack_message(queue_name: str, payload_dict: dict, delay_seconds: int = 30):
    client = await get_queue_client(queue_name)
    await client.send_message(json.dumps(payload_dict), visibility_timeout=delay_seconds)

@app.route(route="webhook", auth_level=func.AuthLevel.ANONYMOUS)
async def webhook(req: func.HttpRequest) -> func.HttpResponse:
    return await webhook_receiver.main(req)

@app.queue_trigger(arg_name="msg", queue_name="incoming-stickers", connection="AzureWebJobsStorage")
async def process_incoming_sticker(msg: func.QueueMessage) -> None:
    body = msg.get_body().decode('utf-8')
    if not body:
        return
    try:
        payload = json.loads(body)
        if not payload:
            return
        await ingestion_worker.process_sticker(payload)
    except DistributedLockError:
        dequeue_count = getattr(msg, 'dequeue_count', 1)
        if dequeue_count >= 5:
            logging.error("Max NACK loops reached for lock contention. Poisoning message natively.")
            raise Exception("Max retries exceeded") from None
        logging.info("Concurrent lock contention. Manually NACKing message for delayed retry.")
        await nack_message("incoming-stickers", payload, delay_seconds=30)
        return
    except Exception as e:
        logging.error(f"Error processing sticker msg. Type: {type(e).__name__}")
        raise Exception(f"Queue payload processing failed: {type(e).__name__}") from None

@app.queue_trigger(arg_name="msg", queue_name="incoming-queries", connection="AzureWebJobsStorage")
async def process_incoming_query(msg: func.QueueMessage) -> None:
    body = msg.get_body().decode('utf-8')
    if not body:
        return
    try:
        payload = json.loads(body)
        if not payload:
            return
        await query_handler.handle_query(payload)
    except Exception as e:
        logging.error(f"Error processing query msg. Type: {type(e).__name__}")
        raise Exception(f"Queue payload processing failed: {type(e).__name__}") from None
