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

async def delete_container():
    async with CosmosClient(config.COSMOS_DB_URL, credential=config.COSMOS_DB_KEY) as client:
        db = client.get_database_client(config.COSMOS_DB_DATABASE)
        try:
            await db.delete_container("local_image_mock")
            print("Successfully deleted local_image_mock container from Cosmos DB")
        except Exception as e:
            print(f"Container might not exist or could not be deleted: {e}")

if __name__ == "__main__":
    asyncio.run(delete_container())
