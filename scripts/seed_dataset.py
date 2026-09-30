import asyncio
import base64
import json
import uuid
import io
import aiohttp
from PIL import Image

# Fetch a tiny batch of 3 sticker-like images (using Pokemon sprites for safety/speed)
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
    
    # Optional: Mock OpenAI if you want fully offline execution without an API key
    import os
    if not os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY") == "<your-real-openai-key>":
        print("OPENAI_API_KEY not set. Mocking OpenAI calls for local test...")
        import src.clients
        
        class DummyEmbeddings:
            async def create(self, model, input):
                class Resp:
                    pass
                resp = Resp()
                resp.data = [{"embedding": [0.1] * 1536}]
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

    print("Fetching sample dataset...")
    stickers = await fetch_sticker_sample()
    print(f"Downloaded {len(stickers)} images. Injecting into local pipeline...")
    
    import src.ingestion_worker
    
    # Mock download_media so it doesn't hit Meta Graph API
    async def mock_download_media(media_id, token):
        for idx, sticker in enumerate(stickers):
            if media_id == f"media_{idx}":
                return sticker
        return stickers[0]
    
    src.ingestion_worker.download_media = mock_download_media
    
    # Seed the local pipeline
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
            print(f"❌ Failed to process sticker {idx}: {e}")

if __name__ == "__main__":
    asyncio.run(seed_stickers())
