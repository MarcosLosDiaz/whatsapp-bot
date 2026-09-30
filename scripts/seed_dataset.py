import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
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

async def fetch_sticker_sample():
    urls = [
        "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png",
        "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png",
        "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/4.png"
    ]
    stickers = []
    async with aiohttp.ClientSession() as session:
        for url in urls:
            async with session.get(url) as resp:
                data = await resp.read()
                img = Image.open(io.BytesIO(data))
                out = io.BytesIO()
                img.save(out, format="WEBP")
                stickers.append(out.getvalue())
    return stickers

async def seed_stickers():
    print("Initializing environment...")
    if not os.environ.get("OPENAI_APIKEY") or os.environ.get("OPENAI_APIKEY") == "<your-real-openai-key>":
        print("OPENAI_APIKEY not set. Mocking OpenAI calls for local test...")
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
    print("Cosmos DB ready.")

    print("Fetching sample dataset...")
    stickers = await fetch_sticker_sample()
    print(f"Downloaded {len(stickers)} images. Injecting into local pipeline...")
    
    import src.ingestion_worker
    async def mock_download_media(media_id, token):
        for idx, sticker in enumerate(stickers):
            if media_id == f"media_{idx}":
                return sticker
        return stickers[0]
    src.ingestion_worker.download_media = mock_download_media
    
    for idx, sticker in enumerate(stickers):
        payload = {
            "user_id": "+15551234567",
            "sticker_id": f"sticker_{idx}",
            "media_id": f"media_{idx}"
        }
        print(f"Processing sticker {idx}...")
        try:
            await src.ingestion_worker.process_sticker(payload)
            print(f"✅ Sticker {idx} successfully indexed in local CosmosDB and Redis!")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"❌ Failed to process sticker {idx}: {e}")

async def test_query():
    print("\n--- Testing E2E Query Retrieval ---")
    import src.query_handler
    sent_stickers = []
    async def mock_send_sticker(user_id, sticker_id):
        sent_stickers.append(sticker_id)
        print(f"✅ Meta API successfully triggered to send sticker {sticker_id} to user {user_id}")
    src.query_handler.send_sticker = mock_send_sticker
    
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
