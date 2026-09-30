import json
import logging
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from openai import APIConnectionError, RateLimitError
from src.clients import get_openai_client
from src.config import config
from src.search import get_search_provider

SYSTEM_PROMPT = """You are a meme extraction bot. Describe the image in detail. Extract the exact text written on the image, preserving all spelling errors and intentional slang. ONLY call the search_web tool if you encounter highly specific, novel internet slang, unknown public figures, or bizarre cultural references that you cannot confidently identify from your pre-training. For generic stickers, animals, common reactions, or standard memes, DO NOT search the web."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Searches the web for obscure internet slang, cultural references, or public figures.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query."
                    }
                },
                "required": ["query"]
            }
        }
    }
]

@retry(wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(10), retry=retry_if_exception_type((APIConnectionError, RateLimitError)))
async def run_vision_agent(b64_image: str) -> str:
    client = await get_openai_client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": "Describe this meme sticker."},
            {"type": "image_url", "image_url": {"url": f"data:image/webp;base64,{b64_image}"}}
        ]}
    ]
    
    max_iterations = 3
    for _ in range(max_iterations):
        response = await client.chat.completions.create(
            model=config.OPENAI_VLM_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto"
        )
        
        msg = response.choices[0].message
        messages.append(msg) # Append the assistant message exactly as-is
        
        if not msg.tool_calls:
            # Done! Agent didn't request any more tools
            return msg.content or ""
            
        # Execute tools
        for tool_call in msg.tool_calls:
            if tool_call.function.name == "search_web":
                args = json.loads(tool_call.function.arguments)
                query = args.get("query", "")
                
                search_provider = get_search_provider()
                search_result = await search_provider.search(query)
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": search_result
                })
                
    # If we hit max iterations, force a final generation without tools
    final_response = await client.chat.completions.create(
        model=config.OPENAI_VLM_MODEL,
        messages=messages,
    )
    return final_response.choices[0].message.content or ""
