import json
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.core.config import settings
from app.db.session import get_db
from app.services.webhook_verify import verify_meta_signature
from app.db.models.wa_number import WhatsAppNumber
from app.db.models.conversation import Conversation
from app.db.models.message import Message, Direction
from app.services.broadcaster import broadcaster

router = APIRouter(prefix="/webhooks/whatsapp")

@router.get("")
async def verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        return int(challenge)
    raise HTTPException(403, "Forbidden")

@router.post("")
async def handle(request: Request, db: AsyncSession = Depends(get_db)):
    raw = await verify_meta_signature(request)
    data = json.loads(raw.decode("utf-8"))

    entry = data.get("entry") or []
    if not entry:
        return {"ok": True}

    changes = entry[0].get("changes") or []
    if not changes:
        return {"ok": True}

    value = changes[0].get("value") or {}
    metadata = value.get("metadata") or {}
    phone_number_id = metadata.get("phone_number_id")
    if not phone_number_id:
        return {"ok": True}

    wa_num = (await db.execute(select(WhatsAppNumber).where(WhatsAppNumber.phone_number_id == phone_number_id))).scalar_one_or_none()
    if not wa_num:
        return {"ok": True}

    messages = value.get("messages") or []
    for m in messages:
        if m.get("type") != "text":
            continue

        from_wa = m.get("from")
        text = (m.get("text") or {}).get("body")
        meta_msg_id = m.get("id")
        ts = m.get("timestamp")
        sent_at = datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts else datetime.now(timezone.utc)

        q = await db.execute(
            select(Conversation).where(
                Conversation.wa_number_id == wa_num.id,
                Conversation.customer_wa_id == from_wa
            )
        )
        conv = q.scalar_one_or_none()
        if not conv:
            conv = Conversation(wa_number_id=wa_num.id, customer_wa_id=from_wa)
            db.add(conv)
            await db.flush()

        conv.last_inbound_at = sent_at
        conv.last_message_at = sent_at

        msg = Message(
            conversation_id=conv.id,
            direction=Direction.IN,
            body=text,
            meta_message_id=meta_msg_id,
            sent_at=sent_at
        )
        db.add(msg)
        await db.commit()

        await broadcaster.broadcast(
            room=f"number:{wa_num.id}",
            payload={"event": "message:new", "conversation_id": conv.id, "text": text, "from": from_wa, "at": sent_at.isoformat()}
        )

    return {"ok": True}
