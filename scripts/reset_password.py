import asyncio
from getpass import getpass
from sqlalchemy import select

from app.db.session import AsyncSessionLocal, engine
from app.db.base import Base
from app.db.models.user import User
from app.core.security import hash_password


async def main():
    # ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    username = input("Username to reset: ").strip()
    new_pass = getpass("New password: ").strip()

    if not new_pass:
        print("Password cannot be empty")
        return

    async with AsyncSessionLocal() as db:
        u = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if not u:
            print("User not found:", username)
            return
        u.password_hash = hash_password(new_pass)
        await db.commit()
        print("Password reset OK for:", username)


if __name__ == "__main__":
    asyncio.run(main())
