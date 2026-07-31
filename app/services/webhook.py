import httpx
from app.core.config import settings
from app.schemas.payment import WebhookPayload


async def send_webhook(webhook_url: str, payload: WebhookPayload) -> bool:
    try:
        async with httpx.AsyncClient(timeout=settings.WEBHOOK_TIMEOUT) as client:
            response = await client.post(webhook_url, json=payload.model_dump())
            return 200 <= response.status_code < 300
    except Exception:
        return False
