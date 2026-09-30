import logging
from src.config import config
from src.clients import get_aiohttp_session

class MessagingProvider:
    async def send_text(self, user_id: str, text: str):
        raise NotImplementedError

    async def send_sticker(self, user_id: str, sticker_id: str):
        raise NotImplementedError

class MetaMessagingProvider(MessagingProvider):
    async def _send_payload(self, payload: dict):
        url = f"https://graph.facebook.com/{config.META_GRAPH_VERSION}/{config.META_PHONE_ID}/messages"
        headers = {
            "Authorization": f"Bearer {config.META_GRAPH_TOKEN}",
            "Content-Type": "application/json"
        }
        session = await get_aiohttp_session()
        async with session.post(url, headers=headers, json=payload) as resp:
            resp.raise_for_status()

    async def send_text(self, user_id: str, text: str):
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": user_id,
            "type": "text",
            "text": {"preview_url": False, "body": text}
        }
        await self._send_payload(payload)

    async def send_sticker(self, user_id: str, sticker_id: str):
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": user_id,
            "type": "sticker",
            "sticker": {"id": sticker_id}
        }
        await self._send_payload(payload)

class TerminalMessagingProvider(MessagingProvider):
    async def send_text(self, user_id: str, text: str):
        print(f"\n[WhatsApp Mock -> {user_id}]: {text}")

    async def send_sticker(self, user_id: str, sticker_id: str):
        print(f"\n[WhatsApp Mock -> {user_id}]: 📎 Sticker ({sticker_id})")
        # Could optionally open it if we download it from Cosmos, but printing ID is fine for mock

_provider = None

def get_messaging_provider() -> MessagingProvider:
    global _provider
    if not _provider:
        if config.DEPLOY_ENV == "local_terminal":
            _provider = TerminalMessagingProvider()
        else:
            _provider = MetaMessagingProvider()
    return _provider
