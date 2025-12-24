import httpx
from app.core.config import settings

GRAPH_BASE = "https://graph.facebook.com"

async def send_text_message(phone_number_id: str, to_wa_id: str, text: str) -> dict:
    url = f"{GRAPH_BASE}/{settings.GRAPH_API_VERSION}/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_wa_id,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()
