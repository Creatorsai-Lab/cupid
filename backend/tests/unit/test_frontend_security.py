from httpx import AsyncClient

from app.config import settings


async def test_frontend_origin_is_allowed(client: AsyncClient) -> None:
    origin = settings.frontend_url.rstrip("/")

    response = await client.get(
        "/health",
        headers={"Origin": origin},
    )

    assert response.headers["access-control-allow-origin"] == origin


async def test_unknown_origin_is_not_allowed(client: AsyncClient) -> None:
    response = await client.get(
        "/health",
        headers={"Origin": "https://attacker.example"},
    )

    assert "access-control-allow-origin" not in response.headers
