from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete
from datetime import datetime, timezone, timedelta

from app.db.session import get_db
from app.db.models.user import User, Role
from app.db.models.assignment import Assignment
from app.db.models.wa_number import WhatsAppNumber
from app.db.models.conversation import Conversation
from app.db.models.message import Message, Direction
from app.core.security import verify_password, hash_password
from app.services.locks import acquire_lock, get_lock_owner, refresh_lock
from app.services.whatsapp_cloud import send_text_message

templates = Jinja2Templates(directory="app/web/templates")
web_router = APIRouter(include_in_schema=False)

SESSION_COOKIE = "wa_session_user"

def redirect(url: str):
    return RedirectResponse(url=url, status_code=302)

async def get_web_user(request: Request, db: AsyncSession) -> User | None:
    username = request.cookies.get(SESSION_COOKIE)
    if not username:
        return None
    q = await db.execute(select(User).where(User.username == username))
    user = q.scalar_one_or_none()
    if not user or not user.is_active:
        return None
    return user

async def require_web_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    user = await get_web_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user

def is_admin(user: User) -> bool:
    return user.role == Role.admin

async def visible_number_ids(db: AsyncSession, user: User) -> list[int]:
    if user.role == Role.admin:
        q = await db.execute(select(WhatsAppNumber.id))
        return [x[0] for x in q.all()]
    q = await db.execute(select(Assignment.wa_number_id).where(Assignment.user_id == user.id))
    return [x[0] for x in q.all()]

@web_router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_web_user(request, db)
    if not user:
        return redirect("/login")
    return redirect("/dashboard")

@web_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@web_router.post("/login")
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(select(User).where(User.username == username))
    user = q.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", {"request": request, "error": "بيانات الدخول غير صحيحة"})

    resp = redirect("/dashboard")
    resp.set_cookie(SESSION_COOKIE, user.username, httponly=True, samesite="lax")
    return resp

@web_router.post("/logout")
async def logout():
    resp = redirect("/login")
    resp.delete_cookie(SESSION_COOKIE)
    return resp

@web_router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: User = Depends(require_web_user), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    ids = await visible_number_ids(db, user)
    conv_count = (await db.execute(select(func.count()).select_from(Conversation).where(Conversation.wa_number_id.in_(ids)))).scalar() or 0
    open_count = (await db.execute(select(func.count()).select_from(Conversation).where(Conversation.wa_number_id.in_(ids), Conversation.status == "open"))).scalar() or 0
    in_total = (await db.execute(
        select(func.count()).select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.wa_number_id.in_(ids), Message.direction == Direction.IN)
    )).scalar() or 0

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "stats": {"conversations": conv_count, "open": open_count, "in_total": in_total},
        "is_admin": is_admin(user),
    })

@web_router.get("/inbox", response_class=HTMLResponse)
async def inbox_page(request: Request, user: User = Depends(require_web_user), db: AsyncSession = Depends(get_db)):
    ids = await visible_number_ids(db, user)
    numbers = (await db.execute(select(WhatsAppNumber).where(WhatsAppNumber.id.in_(ids), WhatsAppNumber.is_active == True).order_by(WhatsAppNumber.id))).scalars().all()
    selected_number_id = int(request.query_params.get("number_id") or (numbers[0].id if numbers else 0)) if numbers else 0

    conversations = []
    if selected_number_id:
        conversations = (await db.execute(
            select(Conversation).where(Conversation.wa_number_id == selected_number_id).order_by(desc(Conversation.last_message_at))
        )).scalars().all()

    selected_conversation_id = int(request.query_params.get("conversation_id") or (conversations[0].id if conversations else 0)) if conversations else 0

    messages = []
    if selected_conversation_id:
        messages = (await db.execute(select(Message).where(Message.conversation_id == selected_conversation_id).order_by(Message.sent_at))).scalars().all()

    err = request.query_params.get("err")

    return templates.TemplateResponse("inbox.html", {
        "request": request,
        "user": user,
        "is_admin": is_admin(user),
        "numbers": numbers,
        "selected_number_id": selected_number_id,
        "conversations": conversations,
        "selected_conversation_id": selected_conversation_id,
        "messages": messages,
        "err": err
    })

async def ensure_conv_access(db: AsyncSession, user: User, conv_id: int) -> Conversation:
    conv = (await db.execute(select(Conversation).where(Conversation.id == conv_id))).scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Not found")
    ids = await visible_number_ids(db, user)
    if conv.wa_number_id not in ids:
        raise HTTPException(403, "Not allowed")
    return conv

@web_router.post("/inbox/lock")
async def inbox_lock(conversation_id: int = Form(...), user: User = Depends(require_web_user), db: AsyncSession = Depends(get_db)):
    conv = await ensure_conv_access(db, user, conversation_id)
    ok = await acquire_lock(conv.id, user.id, ttl_seconds=600)
    if not ok:
        owner = await get_lock_owner(conv.id)
        return redirect(f"/inbox?number_id={conv.wa_number_id}&conversation_id={conv.id}&err=locked_by_{owner}")
    return redirect(f"/inbox?number_id={conv.wa_number_id}&conversation_id={conv.id}")

@web_router.post("/inbox/reply")
async def inbox_reply(conversation_id: int = Form(...), text: str = Form(...), user: User = Depends(require_web_user), db: AsyncSession = Depends(get_db)):
    text = (text or "").strip()
    if not text:
        return redirect(f"/inbox?conversation_id={conversation_id}&err=empty")

    conv = await ensure_conv_access(db, user, conversation_id)

    owner = await get_lock_owner(conv.id)
    if owner is not None and owner != user.id:
        return redirect(f"/inbox?number_id={conv.wa_number_id}&conversation_id={conv.id}&err=locked")
    if owner == user.id:
        await refresh_lock(conv.id, user.id, ttl_seconds=600)

    if conv.last_inbound_at and conv.last_inbound_at < datetime.now(timezone.utc) - timedelta(hours=24):
        return redirect(f"/inbox?number_id={conv.wa_number_id}&conversation_id={conv.id}&err=outside_24h")

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
    return redirect(f"/inbox?number_id={conv.wa_number_id}&conversation_id={conv.id}")

# --- Admin pages (server-rendered) ---
@web_router.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request, user: User = Depends(require_web_user), db: AsyncSession = Depends(get_db)):
    if not is_admin(user):
        return redirect("/dashboard")
    users = (await db.execute(select(User).order_by(User.id))).scalars().all()
    return templates.TemplateResponse("admin_users.html", {"request": request, "user": user, "is_admin": True, "users": users})

@web_router.post("/admin/users")
async def admin_users_create(
    username: str = Form(...),
    name: str = Form(""),
    password: str = Form(...),
    role: str = Form("employee"),
    user: User = Depends(require_web_user),
    db: AsyncSession = Depends(get_db),
):
    if not is_admin(user):
        return redirect("/dashboard")
    u = User(username=username.strip(), name=(name.strip() or username.strip()), password_hash=hash_password(password.strip()), role=Role(role))
    db.add(u)
    await db.commit()
    return redirect("/admin/users")

@web_router.post("/admin/users/{user_id}/toggle")
async def admin_users_toggle(user_id: int, user: User = Depends(require_web_user), db: AsyncSession = Depends(get_db)):
    if not is_admin(user):
        return redirect("/dashboard")
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target:
        target.is_active = not target.is_active
        await db.commit()
    return redirect("/admin/users")

@web_router.get("/admin/numbers", response_class=HTMLResponse)
async def admin_numbers(request: Request, user: User = Depends(require_web_user), db: AsyncSession = Depends(get_db)):
    if not is_admin(user):
        return redirect("/dashboard")
    numbers = (await db.execute(select(WhatsAppNumber).order_by(WhatsAppNumber.id))).scalars().all()
    return templates.TemplateResponse("admin_numbers.html", {"request": request, "user": user, "is_admin": True, "numbers": numbers})

@web_router.post("/admin/numbers")
async def admin_numbers_create(
    display_name: str = Form(...),
    phone_number_id: str = Form(...),
    user: User = Depends(require_web_user),
    db: AsyncSession = Depends(get_db),
):
    if not is_admin(user):
        return redirect("/dashboard")
    n = WhatsAppNumber(display_name=display_name.strip(), phone_number_id=phone_number_id.strip(), is_active=True)
    db.add(n)
    await db.commit()
    return redirect("/admin/numbers")

@web_router.post("/admin/numbers/{number_id}/toggle")
async def admin_numbers_toggle(number_id: int, user: User = Depends(require_web_user), db: AsyncSession = Depends(get_db)):
    if not is_admin(user):
        return redirect("/dashboard")
    n = (await db.execute(select(WhatsAppNumber).where(WhatsAppNumber.id == number_id))).scalar_one_or_none()
    if n:
        n.is_active = not n.is_active
        await db.commit()
    return redirect("/admin/numbers")

@web_router.get("/admin/assignments", response_class=HTMLResponse)
async def admin_assignments(request: Request, user: User = Depends(require_web_user), db: AsyncSession = Depends(get_db)):
    if not is_admin(user):
        return redirect("/dashboard")

    users = (await db.execute(select(User).order_by(User.id))).scalars().all()
    numbers = (await db.execute(select(WhatsAppNumber).order_by(WhatsAppNumber.id))).scalars().all()

    selected_user_id = int(request.query_params.get("user_id") or (users[0].id if users else 0)) if users else 0
    assigned = set()
    if selected_user_id:
        rows = (await db.execute(select(Assignment.wa_number_id).where(Assignment.user_id == selected_user_id))).all()
        assigned = {r[0] for r in rows}

    return templates.TemplateResponse("admin_assignments.html", {
        "request": request, "user": user, "is_admin": True,
        "users": users, "numbers": numbers, "selected_user_id": selected_user_id, "assigned": assigned
    })

@web_router.post("/admin/assignments")
async def admin_assignments_save(
    user_id: int = Form(...),
    wa_number_ids: str = Form(""),
    user: User = Depends(require_web_user),
    db: AsyncSession = Depends(get_db),
):
    if not is_admin(user):
        return redirect("/dashboard")

    # wa_number_ids is comma-separated from UI
    ids = [int(x) for x in wa_number_ids.split(",") if x.strip().isdigit()]

    await db.execute(delete(Assignment).where(Assignment.user_id == user_id))
    for nid in ids:
        db.add(Assignment(user_id=user_id, wa_number_id=nid))
    await db.commit()
    return redirect(f"/admin/assignments?user_id={user_id}")
