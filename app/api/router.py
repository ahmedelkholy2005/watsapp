from fastapi import APIRouter
from app.api.routes import auth, inbox_api, websocket, webhooks_whatsapp, admin_api

api = APIRouter(prefix="/api")
api.include_router(auth.router, tags=["auth"])
api.include_router(inbox_api.router, tags=["inbox"])
api.include_router(admin_api.router, tags=["admin"])
api.include_router(websocket.router, tags=["ws"])
api.include_router(webhooks_whatsapp.router, tags=["webhooks"])
