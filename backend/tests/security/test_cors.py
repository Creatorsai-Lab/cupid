"""Browsers may call the API only from the frontend's origin.

The API uses cookie sessions (allow_credentials=True), so the allowed origin must
be exactly the frontend — never "*" and never an arbitrary site.
"""

import pytest
from httpx import AsyncClient

from app.config import settings

FRONTEND = settings.frontend_url.rstrip("/")


def preflight(origin: str) -> dict[str, str]:
    return {"Origin": origin, "Access-Control-Request-Method": "POST"}


async def test_frontend_origin_may_call_with_credentials(client: AsyncClient):
    response = await client.options(
        "/api/v1/agents/generate", headers=preflight(FRONTEND)
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND
    assert response.headers["access-control-allow-credentials"] == "true"


@pytest.mark.parametrize(
    "origin",
    ["https://evil.example", f"{FRONTEND}.evil.example", "null"],
)
async def test_other_origins_are_refused(client: AsyncClient, origin: str):
    preflight_response = await client.options(
        "/api/v1/agents/generate", headers=preflight(origin)
    )
    simple_response = await client.get("/health", headers={"Origin": origin})

    assert "access-control-allow-origin" not in preflight_response.headers
    assert "access-control-allow-origin" not in simple_response.headers
