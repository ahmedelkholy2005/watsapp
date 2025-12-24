from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.core.config import settings
from app.api.router import api
from app.web.routes import web_router
from app.db.session import engine
from app.db.base import Base

# Import models so Base knows them
from app.db import models  # noqa: F401

app = FastAPI(title=settings.APP_NAME)

@app.on_event("startup")
async def startup():
    # Create tables automatically (simple start). For production, replace with migrations.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.include_router(api)
app.include_router(web_router)
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

@app.get("/health")
def health():
    return {"ok": True}
