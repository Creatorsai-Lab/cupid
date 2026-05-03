"""
YouTube OAuth — Google's authorization code flow, end to end.

═══════════════════════════════════════════════════════════════════════════
TWO FUNCTIONS, TWO RESPONSIBILITIES
═══════════════════════════════════════════════════════════════════════════
build_authorization_url()
    Generates the Google URL we redirect the user to. Includes:
        - our client_id (so Google knows who's asking)
        - the scopes we want (what data we want access to)
        - the redirect_uri (where Google should send them back)
        - the state token (CSRF protection)

exchange_code_for_tokens()
    After Google redirects back with a `code`, we trade that code for
    actual access + refresh tokens by hitting Google's token endpoint.

═══════════════════════════════════════════════════════════════════════════
SCOPES WE REQUEST
═══════════════════════════════════════════════════════════════════════════
Three scopes for the analytics use case:

  youtube.readonly
      Read channel metadata, video lists, basic stats.
      Required for "show my channel info."

  yt-analytics.readonly
      Detailed analytics: views, watch time, audience demographics.
      Required for the dashboard charts.

  userinfo.email
      So we can identify the Google account that connected.
      Useful for displaying "connected as user@gmail.com" in the UI.

We deliberately do NOT request youtube.upload or anything that lets us
modify the user's channel. Read-only is the principle of least privilege:
ask for the minimum access needed.

═══════════════════════════════════════════════════════════════════════════
NOTE ON access_type=offline AND prompt=consent
═══════════════════════════════════════════════════════════════════════════
Google issues refresh tokens ONLY if access_type=offline. We need refresh
tokens because access tokens expire in 1 hour but our background sync
runs every 6 hours.

prompt=consent forces Google to re-show the consent screen even for users
who've connected before. This guarantees we get a refresh token on every
flow (Google sometimes omits it on subsequent connects).
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TypedDict
from urllib.parse import urlencode

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


# ─── Constants ─────────────────────────────────────────────────

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"

# Space-separated list of scopes we request
SCOPES = " ".join([
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
])


# ─── Type definitions ──────────────────────────────────────────

class TokenResponse(TypedDict):
    access_token: str
    refresh_token: str | None     # might be missing on re-auth
    expires_in: int               # seconds until expiry
    scope: str                    # space-separated granted scopes
    token_type: str               # always "Bearer" in practice


class ChannelInfo(TypedDict):
    channel_id: str
    handle: str | None
    title: str
    email: str


# ─── Step 1: Build the auth URL ────────────────────────────────

def build_authorization_url(state: str) -> str:
    """
    Generate the Google OAuth URL we redirect the user to.

    The user's browser will hit this URL, see Google's consent screen,
    and (if they approve) be redirected back to our callback.
    """
    params = {
        "client_id":     settings.google_client_id,
        "redirect_uri":  settings.google_redirect_uri,
        "response_type": "code",
        "scope":         SCOPES,
        "access_type":   "offline",     # required for refresh_token
        "prompt":        "consent",     # always show consent → guarantees refresh_token
        "state":         state,         # CSRF protection
        "include_granted_scopes": "true",
    }

    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


# ─── Step 2: Exchange code for tokens ──────────────────────────

async def exchange_code_for_tokens(code: str) -> TokenResponse:
    """
    Trade Google's auth `code` for actual tokens.

    This is a server-to-server POST. Google's response includes:
        - access_token (1 hour life)
        - refresh_token (long-lived, until user revokes)
        - expires_in (seconds)
        - scope (what was actually granted — may be subset of requested)
    """
    payload = {
        "code":          code,
        "client_id":     settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri":  settings.google_redirect_uri,
        "grant_type":    "authorization_code",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(GOOGLE_TOKEN_URL, data=payload)

    if response.status_code != 200:
        logger.error(
            "[oauth.youtube] token exchange failed: %d %s",
            response.status_code, response.text[:300],
        )
        raise RuntimeError(
            f"Google token exchange failed (HTTP {response.status_code})"
        )

    return response.json()


# ─── Refresh expired access tokens ─────────────────────────────

async def refresh_access_token(refresh_token: str) -> TokenResponse:
    """
    Use a refresh_token to get a new access_token without user interaction.

    Called by our YouTube API client whenever the cached access_token
    has expired.

    Note: the response usually does NOT include a new refresh_token —
    keep using the existing one until it gets revoked.
    """
    payload = {
        "refresh_token": refresh_token,
        "client_id":     settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "grant_type":    "refresh_token",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(GOOGLE_TOKEN_URL, data=payload)

    if response.status_code != 200:
        # 400 here usually means the refresh_token was revoked by the user.
        # Caller should mark the connection as failed and prompt reconnect.
        logger.warning(
            "[oauth.youtube] refresh failed: %d %s",
            response.status_code, response.text[:200],
        )
        raise RuntimeError(
            f"Token refresh failed (HTTP {response.status_code}) — "
            f"user may have revoked access"
        )

    return response.json()


# ─── Step 3: Get the connected channel info ────────────────────

async def get_connected_channel_info(access_token: str) -> ChannelInfo:
    """
    Right after token exchange, find out WHICH YouTube channel the user
    just connected. Returns the channel ID, handle, title, and email.

    This is two API calls:
        - GET /oauth2/v2/userinfo for the email
        - GET /youtube/v3/channels?mine=true for the channel
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Get user's email
        userinfo_resp = await client.get(GOOGLE_USERINFO_URL, headers=headers)
        userinfo_resp.raise_for_status()
        email = userinfo_resp.json().get("email", "")

        # Get user's primary YouTube channel
        channels_resp = await client.get(
            GOOGLE_CHANNELS_URL,
            headers=headers,
            params={"part": "snippet", "mine": "true"},
        )
        channels_resp.raise_for_status()
        channels_data = channels_resp.json()

    items = channels_data.get("items", [])
    if not items:
        raise RuntimeError(
            "No YouTube channel found for this Google account. "
            "Make sure the account has a channel created."
        )

    channel = items[0]
    snippet = channel.get("snippet", {})

    return {
        "channel_id": channel["id"],
        "handle":     snippet.get("customUrl"),  # e.g. "@CupidTestChannel"
        "title":      snippet.get("title", ""),
        "email":      email,
    }


# ─── Helper: compute when a token expires ──────────────────────

def compute_expires_at(expires_in: int) -> datetime:
    """
    Convert Google's `expires_in` (seconds from now) to an absolute time.

    We subtract a 60-second safety buffer so we refresh slightly early
    rather than discovering expiry mid-API-call.
    """
    return datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)