import os
import logging
from abc import ABC, abstractmethod
import aiohttp
from src.config import config

class SearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str) -> str:
        pass

class BingSearchProvider(SearchProvider):
    async def search(self, query: str) -> str:
        if not config.BING_API_KEY:
            logging.warning("BING_API_KEY is not set. Returning empty search results.")
            return "No results."
            
        headers = {"Ocp-Apim-Subscription-Key": config.BING_API_KEY}
        params = {"q": query, "textDecorations": True, "textFormat": "HTML"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.bing.microsoft.com/v7.0/search", headers=headers, params=params) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    
                    snippets = []
                    for page in data.get("webPages", {}).get("value", [])[:3]: # Keep top 3 snippets
                        snippets.append(page.get("snippet", ""))
                    return " ".join(snippets) if snippets else "No results found."
        except Exception as e:
            logging.error(f"Bing Search API failed: {e}")
            return "Search failed."

class MockSearchProvider(SearchProvider):
    async def search(self, query: str) -> str:
        logging.info(f"[MockSearchProvider] Searching for: {query}")
        return f"[MOCK RESULT] Information about {query}: It is a very rare internet phenomenon."

def get_search_provider() -> SearchProvider:
    if config.DEPLOY_ENV in ['local', 'local_terminal'] and not config.BING_API_KEY:
        return MockSearchProvider()
    return BingSearchProvider()
