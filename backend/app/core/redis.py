"""
Redis client setup.

Provides a singleton async Redis client and a FastAPI dependency.

The singleton pattern ensures we don't open a new connection per request.
Redis maintains a connection pool internally — we just need one client
instance shared across the app.
"""
from __future__ import annotations

from redis.asyncio import Redis

from app.config import settings

# Module-level singleton — created once when this module is first imported.
# `decode_responses=True` means every read returns str, not bytes.
redis_client: Redis = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    encoding="utf-8",
)


async def get_redis() -> Redis:
    """
    FastAPI dependency that yields the shared Redis client.

    Used in routes:
        @router.get("/something")
        async def handler(redis: Redis = Depends(get_redis)):
            await redis.get(...)
    """
    return redis_client


async def close_redis() -> None:
    """Call this from FastAPI's shutdown event to cleanly close connections."""
    await redis_client.aclose()