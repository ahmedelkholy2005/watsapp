import redis.asyncio as redis
from app.core.config import settings

r = redis.from_url(settings.REDIS_URL, decode_responses=True)

def lock_key(conversation_id: int) -> str:
    return f"conv_lock:{conversation_id}"

async def acquire_lock(conversation_id: int, user_id: int, ttl_seconds: int = 600) -> bool:
    return await r.set(lock_key(conversation_id), str(user_id), nx=True, ex=ttl_seconds) is True

async def refresh_lock(conversation_id: int, user_id: int, ttl_seconds: int = 600) -> bool:
    k = lock_key(conversation_id)
    current = await r.get(k)
    if current != str(user_id):
        return False
    await r.expire(k, ttl_seconds)
    return True

async def get_lock_owner(conversation_id: int) -> int | None:
    v = await r.get(lock_key(conversation_id))
    return int(v) if v else None

async def release_lock(conversation_id: int, user_id: int) -> bool:
    k = lock_key(conversation_id)
    current = await r.get(k)
    if current != str(user_id):
        return False
    await r.delete(k)
    return True
