import azure.functions as func
import json
import logging
import os

DEPLOY_ENV = os.environ.get("DEPLOY_ENV", "local")

# Telemetry: Jaeger (local) vs App Insights (azure)
try:
    if DEPLOY_ENV in ["local", "local_terminal"]:
        # Local: export traces to Jaeger via OTLP
        otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otel_endpoint:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            
            from opentelemetry.sdk.resources import Resource
            provider = TracerProvider(resource=Resource.create({"service.name": "whatsapp-bot"}))
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint)))
            trace.set_tracer_provider(provider)
            logging.info(f"OpenTelemetry configured: exporting to Jaeger at {otel_endpoint}")
        else:
            logging.info("OTEL_EXPORTER_OTLP_ENDPOINT not set. Telemetry disabled for local dev.")
    else:
        # Azure: export to Application Insights
        if os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING'):
            from azure.monitor.opentelemetry import configure_azure_monitor
            configure_azure_monitor()
        else:
            logging.warning("APPLICATIONINSIGHTS_CONNECTION_STRING is missing. Telemetry is disabled.")
except Exception as e:
    logging.warning(f"Failed to configure telemetry: {type(e).__name__}")

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
