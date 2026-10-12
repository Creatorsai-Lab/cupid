"""Every route requires a signed-in user unless it is deliberately public.

A new route that forgets `CurrentUser` / `get_current_user` fails here. To make
a route public on purpose, add it to PUBLIC_ROUTES with the reason.
"""

import re

import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient

from app.main import app

PUBLIC_ROUTES = {
    ("GET", "/health"): "uptime check",
    ("GET", "/api/v1/auth/google/login"): "starts sign-in",
    (
        "GET",
        "/api/v1/auth/google/callback",
    ): "Google redirect; protected by OAuth state",
    ("POST", "/api/v1/auth/logout"): "clears the cookie; harmless without one",
    ("GET", "/api/v1/connections/youtube/callback"): (
        "Google redirect; protected by OAuth state"
    ),
}

ROUTES = sorted(
    (method, route.path)
    for route in app.routes
    if isinstance(route, APIRoute)
    for method in route.methods - {"HEAD"}
)
PROTECTED = [r for r in ROUTES if r not in PUBLIC_ROUTES]


def test_public_allowlist_has_no_stale_entries():
    assert set(PUBLIC_ROUTES) <= set(ROUTES)


@pytest.mark.parametrize(("method", "path"), PROTECTED, ids=lambda v: v)
async def test_route_rejects_requests_without_login(
    client: AsyncClient, method: str, path: str
):
    url = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)
    response = await client.request(method, url, json={})
    assert response.status_code == 401
