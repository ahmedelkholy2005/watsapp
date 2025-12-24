# WA Inbox (Python + FastAPI + Jinja2 "Blade-like")

Shared inbox for ~50 WhatsApp Business numbers and ~48 employees with:
- Admin / Employee roles
- Assign numbers to employees (visibility + access control)
- Inbox UI (server-rendered templates)
- WhatsApp Cloud API webhook receiver (with signature verification)
- Reply endpoint (reply-only, enforces 24h window)
- Conversation locking via Redis to prevent double replies
- Realtime updates via WebSocket (simple room broadcast)

## 1) Setup
Copy `.env.example` to `.env` and fill values.

Start Postgres + Redis:
```bash
docker compose up -d
```

Install deps:
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Run
```bash
uvicorn app.main:app --reload --port 8000
```

Open:
- http://localhost:8000/login

## 3) Create first admin user
Use the helper script:
```bash
python scripts/create_admin.py
```
It will prompt for username/password.

## 4) WhatsApp Cloud API Webhook
- Verification URL (GET): `http(s)://<your-host>/api/webhooks/whatsapp`
- Webhook receiver (POST): same URL
- Set `WHATSAPP_VERIFY_TOKEN` in `.env`
- Set `META_APP_SECRET` in `.env` for signature validation
- Add your Meta `phone_number_id` entries in Admin -> Numbers

## Notes
- UI sessions use a simple cookie storing the username (for demo). For production, replace with signed cookies / server-side sessions.
- The webhook parser currently handles text messages. Extend for media if needed.
