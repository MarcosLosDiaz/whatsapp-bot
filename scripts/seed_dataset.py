import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
os.environ["DEPLOY_ENV"] = "local_terminal"
def load_local_settings():
    try:
        with open(os.path.join(os.path.dirname(__file__), "..", "local.settings.json"), "r") as f:
            settings = json.load(f)
            for k, v in settings.get("Values", {}).items():
                if k not in os.environ:
                    os.environ[k] = str(v)
    except:
        pass
load_local_settings()

import asyncio
import base64
import uuid
import io
import aiohttp
from PIL import Image


async def fetch_sticker_batch(start_idx, end_idx):
    stickers = []
    async with aiohttp.ClientSession() as session:
        for idx in range(start_idx, end_idx + 1):
            url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{idx}.png"
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.read()
                    img = Image.open(io.BytesIO(data))
                    out = io.BytesIO()
                    img.save(out, format="WEBP")
                    stickers.append((f"pokemon_{idx}", out.getvalue()))
            except Exception as e:
                pass
    return stickers


async def seed_stickers():
    print("Initializing environment...")
    if not os.environ.get("OPENAI_APIKEY") or os.environ.get("OPENAI_APIKEY") == "<your-real-openai-key>":
        print("OPENAI_APIKEY not set. Mocking OpenAI calls for local test...")
        os.environ["OPENAI_APIKEY"] = "dummy_offline_key_to_bypass_validation"
        import src.clients
        class DummyEmbeddingObject:
            def __init__(self):
                self.embedding = [0.1] * 1536
        class DummyEmbeddings:
            async def create(self, model, input):
                class Resp:
                    pass
                resp = Resp()
                resp.data = [DummyEmbeddingObject()]
                return resp
        class DummyChat:
            class completions:
                @staticmethod
                async def create(model, messages):
                    class Msg:
                        content = "A beautiful mocked sticker."
                    class Choice:
                        message = Msg()
                    class Resp:
                        choices = [Choice()]
                    return Resp()
        class DummyOpenAIClient:
            def __init__(self):
                self.embeddings = DummyEmbeddings()
                self.chat = DummyChat()
        async def mock_get_openai_client():
            return DummyOpenAIClient()
        src.clients.get_openai_client = mock_get_openai_client

    from src.config import config
    from azure.cosmos.aio import CosmosClient
    from azure.cosmos import PartitionKey
    
    
    print("Setting up Cosmos DB Emulator databases...")
    async with CosmosClient(config.COSMOS_DB_URL, credential=config.COSMOS_DB_KEY) as client:
        db = await client.create_database_if_not_exists(id=config.COSMOS_DB_DATABASE)
        await db.create_container_if_not_exists(id="stickers", partition_key=PartitionKey(path="/id"))
        await db.create_container_if_not_exists(id="user_stickers", partition_key=PartitionKey(path="/userId"))
        img_container = await db.create_container_if_not_exists(id="local_image_mock", partition_key=PartitionKey(path="/id"))
    print("Cosmos DB ready.")


    
    print("Fetching sample dataset (1000 pokemon)...")
    
    # We will process in chunks of 50 to avoid overloading memory/rate limits
    total = 1000
    chunk_size = 50
    import src.ingestion_worker
    
    for i in range(1, total + 1, chunk_size):
        end_idx = min(i + chunk_size - 1, total)
        print(f"\\n--- Processing Batch {i} to {end_idx} ---")
        
        batch_stickers = await fetch_sticker_batch(i, end_idx)
        
        async def mock_download_media(media_id, token):
            for s_id, s_data in batch_stickers:
                if media_id == f"media_{s_id}":
                    return s_data
            return batch_stickers[0][1]
            
        src.ingestion_worker.download_media = mock_download_media
        
        # Save to local_image_mock Cosmos container
        from azure.cosmos.aio import CosmosClient
        async with CosmosClient(config.COSMOS_DB_URL, credential=config.COSMOS_DB_KEY) as client:
            db = client.get_database_client(config.COSMOS_DB_DATABASE)
            img_container = db.get_container_client("local_image_mock")
            
            for s_id, s_data in batch_stickers:
                b64 = base64.b64encode(s_data).decode('utf-8')
                await img_container.upsert_item({"id": s_id, "data": b64})
                
        # Process them concurrently
        async def process_single(s_id, s_data):
            payload = {
                "user_id": "+15551234567",
                "sticker_id": s_id,
                "media_id": f"media_{s_id}"
            }
            try:
                await src.ingestion_worker.process_sticker(payload)
                print(f"✅ {s_id} indexed!")
            except Exception as e:
                print(f"❌ Failed {s_id}: {type(e).__name__}")
                
        tasks = [process_single(s_id, s_data) for s_id, s_data in batch_stickers]
        await asyncio.gather(*tasks)


async def test_query():
    print("\n--- Testing E2E Query Retrieval ---")
    import src.query_handler
    sent_stickers = []
    async def mock_send_sticker(user_id, sticker_id):
        sent_stickers.append(sticker_id)
        print(f"✅ Meta API successfully triggered to send sticker {sticker_id} to user {user_id}")
    import src.messaging
    class DummyMessagingProvider:
        async def send_text(self, uid, text): pass
        async def send_sticker(self, uid, sid):
            await mock_send_sticker(uid, sid)
    import src.query_handler
    src.query_handler.get_messaging_provider = lambda: DummyMessagingProvider()
    
    query_payload = {
        "user_id": "+15551234567",
        "query": "show me a cool sticker"
    }
    print(f"User searched for: '{query_payload['query']}'")
    await src.query_handler.handle_query(query_payload)
    
    if sent_stickers:
        print(f"🎉 E2E Test Passed! Bot found and returned: {sent_stickers}")
    else:
        print("❌ E2E Test Failed! Bot did not return any stickers.")

async def main():
    await seed_stickers()
    await test_query()

if __name__ == "__main__":
    asyncio.run(main())
