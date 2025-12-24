from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime, timedelta, timezone

from app.db.session import get_db
from app.core.deps_api import get_current_user_api
from app.db.models.user import User, Role
from app.db.models.assignment import Assignment
from app.db.models.wa_number import WhatsAppNumber
from app.db.models.conversation import Conversation
from app.db.models.message import Message, Direction
from app.services.locks import acquire_lock, get_lock_owner, refresh_lock
from app.services.whatsapp_cloud import send_text_message

router = APIRouter(prefix="/inbox")

async def allowed_number_ids(db: AsyncSession, user: User) -> list[int]:
    if user.role == Role.admin:
        q = await db.execute(select(WhatsAppNumber.id))
        return [x[0] for x in q.all()]
    q = await db.execute(select(Assignment.wa_number_id).where(Assignment.user_id == user.id))
    return [x[0] for x in q.all()]

@router.get("/numbers")
async def list_numbers(user: User = Depends(get_current_user_api), db: AsyncSession = Depends(get_db)):
    ids = await allowed_number_ids(db, user)
    q = await db.execute(select(WhatsAppNumber).where(WhatsAppNumber.id.in_(ids)).order_by(WhatsAppNumber.id))
    return q.scalars().all()

@router.post("/conversations/{conversation_id}/lock")
async def lock_conversation(conversation_id: int, user: User = Depends(get_current_user_api)):
    ok = await acquire_lock(conversation_id, user.id, ttl_seconds=600)
    if not ok:
        owner = await get_lock_owner(conversation_id)
        raise HTTPException(409, detail={"locked_by": owner})
    return {"ok": True, "locked_by": user.id, "ttl": 600}

@router.post("/conversations/{conversation_id}/reply")
async def reply(conversation_id: int, payload: dict, user: User = Depends(get_current_user_api), db: AsyncSession = Depends(get_db)):
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text required")

    conv = (await db.execute(select(Conversation).where(Conversation.id == conversation_id))).scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Not found")

    ids = await allowed_number_ids(db, user)
    if conv.wa_number_id not in ids:
        raise HTTPException(403, "Not allowed")

    owner = await get_lock_owner(conversation_id)
    if owner is not None and owner != user.id:
        raise HTTPException(409, detail={"locked_by": owner})
    if owner == user.id:
        await refresh_lock(conversation_id, user.id, ttl_seconds=600)

    if conv.last_inbound_at and conv.last_inbound_at < datetime.now(timezone.utc) - timedelta(hours=24):
        raise HTTPException(400, "Outside 24-hour window (template required)")

    wa_num = (await db.execute(select(WhatsAppNumber).where(WhatsAppNumber.id == conv.wa_number_id))).scalar_one()
    res = await send_text_message(wa_num.phone_number_id, conv.customer_wa_id, text)

    meta_id = None
    try:
        meta_id = res.get("messages", [{}])[0].get("id")
    except Exception:
        pass

    msg = Message(conversation_id=conv.id, direction=Direction.OUT, body=text, meta_message_id=meta_id)
    db.add(msg)
    conv.last_message_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True, "meta": res}
