import asyncio
from azure.cosmos.aio import CosmosClient

async def main():
    client = CosmosClient("http://localhost:8081", credential=(
        "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
    ))
    db = client.get_database_client("WhatsAppBot")
    container = db.get_container_client("stickers")
    
    try:
        # Create a dummy array of 1536 floats (OpenAI embedding size)
        vector = [0.1] * 1536
        query = f"SELECT TOP 5 c.id, VectorDistance(c.embedding, {vector}) AS score FROM c ORDER BY VectorDistance(c.embedding, {vector})"
        results = [item async for item in container.query_items(query=query)]
        print("Success:", results)
    except Exception as e:
        print("Error:", e)
    
    await client.close()

asyncio.run(main())
