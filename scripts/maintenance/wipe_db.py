import sys
import os
import json

try:
    with open("local.settings.json", "r") as f:
        settings = json.load(f)
        for k, v in settings.get("Values", {}).items():
            if k not in os.environ:
                os.environ[k] = str(v)
except:
    pass
os.environ["OPENAI_APIKEY"] = "dummy"
import asyncio
from azure.cosmos.aio import CosmosClient
from src.config import config
from src.clients import get_redis_client

async def wipe():
    # Clear Cosmos containers
    async with CosmosClient(config.COSMOS_DB_URL, credential=config.COSMOS_DB_KEY) as client:
        db = client.get_database_client(config.COSMOS_DB_DATABASE)
        for container_name in ["stickers", "user_stickers"]:
            try:
                await db.delete_container(container_name)
                print(f"Deleted {container_name} from Cosmos DB")
            except Exception:
                pass
                
    # Clear Redis
    redis = await get_redis_client()
    await redis.flushall()
    print("Flushed Redis")

if __name__ == "__main__":
    asyncio.run(wipe())
