import asyncio
from getpass import getpass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import AsyncSessionLocal, engine
from app.db.base import Base
from app.db.models.user import User, Role
from app.core.security import hash_password

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    username = input("Admin username: ").strip()
    name = input("Admin name (optional): ").strip() or username
    password = getpass("Admin password: ").strip()

    async with AsyncSessionLocal() as db:  # type: AsyncSession
        existing = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if existing:
            print("User already exists.")
            return
        u = User(username=username, name=name, password_hash=hash_password(password), role=Role.admin, is_active=True)
        db.add(u)
        await db.commit()
        print("Admin created:", username)

if __name__ == "__main__":
    asyncio.run(main())
