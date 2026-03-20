import httpx
import asyncio

DEFAULT_HEADERS = {
    "User-Agent": "Cupid-Agent/1.0",
    "Accept": "application/json"
}

TIMEOUT = httpx.Timeout(
    connect=5.0,
    read=10.0,
    write=10.0,
    pool=5.0
)

LIMITS = httpx.Limits(
    max_connections=20,
    max_keepalive_connections=10
)

client = httpx.AsyncClient(
    headers=DEFAULT_HEADERS,
    timeout=TIMEOUT,
    limits=LIMITS
)

async def close_client():
    await client.aclose()