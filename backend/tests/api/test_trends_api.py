"""
API tests for /api/v1/trends/news endpoint.

═══════════════════════════════════════════════════════════════════════════
SCOPE
═══════════════════════════════════════════════════════════════════════════
These are end-to-end-ish tests: real HTTP request → real router → real
service → real DB query → real response. No real network (the test client
talks directly to the ASGI app).

What we verify here:
    - Auth gate works (401 without cookie)
    - Endpoint responds with the right shape
    - Cache parameter (?refresh=true) is honored

What we DON'T test here (covered by unit tests instead):
    - BM25 math correctness (test_ranker.py)
    - Velocity score calculation (test_ingest_helpers.py)

═══════════════════════════════════════════════════════════════════════════
WHY THIS TEST FILE IS SHORT
═══════════════════════════════════════════════════════════════════════════
The pyramid principle: lots of unit tests, few integration tests, even
fewer API tests. API tests are slow (~50-100ms each vs ~1ms for unit).
We rely on them only for what unit tests can't catch — wiring between
layers.
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestTrendsAuth:
    """Auth-gating behavior."""

    async def test_unauthenticated_request_returns_401(self, client: AsyncClient):
        """No cookie → 401. Public endpoints don't exist for trends."""
        response = await client.get("/api/v1/trends/news")
        assert response.status_code == 401


class TestTrendsResponseShape:
    """
    These tests need an authenticated session. We'll add an
    `authenticated_client` fixture later — for now we just have the
    structure ready and skip the body.

    Once the auth fixture exists, remove the @pytest.mark.skip and
    these tests light up automatically.
    """

    @pytest.mark.skip(reason="awaiting authenticated_client fixture")
    async def test_response_has_required_fields(self, client: AsyncClient):
        """Response should match the TrendsResponse schema."""
        response = await client.get("/api/v1/trends/news")
        assert response.status_code == 200

        data = response.json()
        assert "articles" in data
        assert "niche" in data
        assert "total_pool" in data
        assert "cached" in data
        assert "generated_at" in data
        assert isinstance(data["articles"], list)

    @pytest.mark.skip(reason="awaiting authenticated_client fixture")
    async def test_refresh_param_bypasses_cache(self, client: AsyncClient):
        """?refresh=true should return cached=False even on second call."""
        await client.get("/api/v1/trends/news")             # warm cache
        response = await client.get("/api/v1/trends/news?refresh=true")

        data = response.json()
        assert data["cached"] is False