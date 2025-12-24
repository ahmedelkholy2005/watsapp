import hmac, hashlib
from fastapi import HTTPException, Request
from app.core.config import settings

async def verify_meta_signature(request: Request) -> bytes:
    sig = request.headers.get("X-Hub-Signature-256")
    if not sig or not sig.startswith("sha256="):
        raise HTTPException(status_code=403, detail="Missing signature")

    raw = await request.body()
    received = sig.split("=", 1)[1]
    expected = hmac.new(settings.META_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, received):
        raise HTTPException(status_code=403, detail="Invalid signature")

    return raw
