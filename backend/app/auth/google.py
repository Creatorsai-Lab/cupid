"""
Google identity — the OAuth2 authorization-code dance for *login*.

Three small steps: build the consent URL, exchange the returned code for
tokens, then fetch the verified profile. We read the profile from Google's
userinfo endpoint over TLS (so it's authentically Google) rather than verifying
the id_token signature ourselves — simpler, and equally trustworthy here.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def build_auth_url(state: str) -> str:
    """The Google consent screen URL we redirect the user to."""
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_login_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict[str, Any]:
    """Swap the authorization code for an access token."""
    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_login_redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data=data)
        resp.raise_for_status()
        return resp.json()


async def fetch_userinfo(access_token: str) -> dict[str, Any]:
    """Get the verified profile: {sub, email, email_verified, name, picture}."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()
