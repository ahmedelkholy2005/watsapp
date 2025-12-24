from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.session import get_db
from app.core.deps_api import get_current_user_api, require_admin_api
from app.db.models.user import User, Role
from app.db.models.wa_number import WhatsAppNumber
from app.db.models.assignment import Assignment
from app.core.security import hash_password

router = APIRouter(prefix="/admin")

@router.get("/users")
async def users(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin_api)):
    q = await db.execute(select(User).order_by(User.id))
    return q.scalars().all()

@router.post("/users")
async def create_user(payload: dict, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin_api)):
    username = (payload.get("username") or "").strip()
    name = (payload.get("name") or username).strip()
    password = (payload.get("password") or "").strip()
    role = payload.get("role") or "employee"
    if not username or not password:
        raise HTTPException(400, "username/password required")
    u = User(username=username, name=name, password_hash=hash_password(password), role=Role(role))
    db.add(u)
    await db.commit()
    return {"ok": True, "id": u.id}

@router.get("/numbers")
async def numbers(db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin_api)):
    q = await db.execute(select(WhatsAppNumber).order_by(WhatsAppNumber.id))
    return q.scalars().all()

@router.post("/numbers")
async def create_number(payload: dict, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin_api)):
    display_name = (payload.get("display_name") or "").strip()
    phone_number_id = (payload.get("phone_number_id") or "").strip()
    if not display_name or not phone_number_id:
        raise HTTPException(400, "display_name/phone_number_id required")
    n = WhatsAppNumber(display_name=display_name, phone_number_id=phone_number_id, is_active=True)
    db.add(n)
    await db.commit()
    return {"ok": True, "id": n.id}

@router.post("/assign")
async def assign(payload: dict, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin_api)):
    user_id = int(payload.get("user_id"))
    number_ids = payload.get("wa_number_ids") or []
    # delete old
    await db.execute(delete(Assignment).where(Assignment.user_id == user_id))
    for nid in number_ids:
        db.add(Assignment(user_id=user_id, wa_number_id=int(nid)))
    await db.commit()
    return {"ok": True}
