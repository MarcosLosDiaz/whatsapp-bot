import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import json
def load_local_settings():
    try:
        with open("local.settings.json", "r") as f:
            settings = json.load(f)
            for k, v in settings.get("Values", {}).items():
                if k not in os.environ:
                    os.environ[k] = str(v)
    except:
        pass
load_local_settings()

os.environ["DEPLOY_ENV"] = "local_terminal"

import asyncio
from src.query_handler import handle_query

# Optional mock if OPENAI_API_KEY is not set
if not os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY") == "<your-real-openai-key>":
    print("⚠️ OPENAI_API_KEY not set. Using dummy vectors for search.")
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
    class DummyOpenAIClient:
        def __init__(self):
            self.embeddings = DummyEmbeddings()
    async def mock_get_openai_client():
        return DummyOpenAIClient()
    src.clients.get_openai_client = mock_get_openai_client
    import src.query_handler
    src.query_handler.get_openai_client = mock_get_openai_client

async def main():
    print("========================================")
    print("📱 WhatsApp Local Terminal Mock 📱")
    print("Type your sticker search prompt below.")
    print("Type 'exit' to quit.")
    print("========================================")
    
    while True:
        try:
            prompt = input("\nYou> ")
            if prompt.lower() in ['exit', 'quit']:
                break
            if not prompt.strip():
                continue
            
            payload = {
                "user_id": "+15551234567",
                "query": prompt
            }
            
            await handle_query(payload)
        except KeyboardInterrupt:
            break
        except EOFError:
            break
        except Exception as e:
            print(f"[System Error]: {e}")

if __name__ == "__main__":
    asyncio.run(main())
