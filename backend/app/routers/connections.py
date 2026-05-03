"""
Connections Router — HTTP endpoints for managing social media connections.

═══════════════════════════════════════════════════════════════════════════
ENDPOINTS
═══════════════════════════════════════════════════════════════════════════
GET    /api/v1/connections/                          → list user's connections
GET    /api/v1/connections/youtube/connect           → start YouTube OAuth
GET    /api/v1/connections/youtube/callback          → OAuth callback target
DELETE /api/v1/connections/{connection_id}           → disconnect

The connect endpoint returns a JSON payload with the auth URL, NOT a
redirect. The frontend opens it in a new tab so the user's Cupid session
isn't disrupted by the Google round-trip.

═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connections import youtube_oauth
from app.connections.oauth_state import (
    consume_state, generate_state_token, store_state,
)
from app.connections.token_crypto import encrypt_token
from app.core.db import get_db
from app.core.redis import get_redis
from app.models.social_connection import SocialConnection
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.connections import (
    ConnectionResponse, ConnectionStartResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connections", tags=["connections"])


# ─── List connected platforms ──────────────────────────────────

@router.get("/", response_model=list[ConnectionResponse])
async def list_connections(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ConnectionResponse]:
    """Return all platforms the current user has connected."""
    stmt = select(SocialConnection).where(
        SocialConnection.user_id == current_user.id
    )
    result = await session.execute(stmt)
    connections = result.scalars().all()

    return [
        ConnectionResponse.model_validate(c, from_attributes=True)
        for c in connections
    ]


# ─── Start the OAuth flow ──────────────────────────────────────

@router.get("/youtube/connect", response_model=ConnectionStartResponse)
async def start_youtube_connection(
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> ConnectionStartResponse:
    """
    Generate a YouTube OAuth URL and return it to the frontend.

    The frontend will open this URL in a new tab/window. The user
    consents on Google's side, then Google redirects to our callback.
    """
    # Generate a one-time CSRF token tied to this user
    state = generate_state_token()
    await store_state(redis, state, str(current_user.id), "youtube")

    auth_url = youtube_oauth.build_authorization_url(state)

    return ConnectionStartResponse(authorization_url=auth_url)


# ─── OAuth callback target ─────────────────────────────────────

@router.get("/youtube/callback", response_class=HTMLResponse)
async def youtube_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    redis: Redis = Depends(get_redis),
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """
    Google redirects here after the user approves (or rejects).

    On success: exchange the code for tokens, fetch channel info,
    encrypt and store everything, and return a "you can close this tab"
    HTML page.

    On any failure: return an HTML error page. Do NOT raise HTTPException
    — the user's browser doesn't render JSON 500s gracefully.

    NOTE: this endpoint does NOT use get_current_user. The user got here
    via Google's redirect, not via our frontend, so there's no JWT cookie
    necessarily attached. We identify the user via the state token.
    """
    # Reject obvious errors first
    if error:
        return _close_window_html(
            success=False,
            message=f"Google denied access: {error}",
        )

    if not code or not state:
        return _close_window_html(
            success=False,
            message="OAuth callback missing required parameters",
        )

    # Validate the state — gives us the user_id who started this flow
    user_id_str = await consume_state(redis, state, expected_platform="youtube")
    if not user_id_str:
        return _close_window_html(
            success=False,
            message="OAuth state invalid or expired. Please try again.",
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        return _close_window_html(success=False, message="Invalid state payload")

    # Exchange code for tokens
    try:
        tokens = await youtube_oauth.exchange_code_for_tokens(code)
    except RuntimeError as exc:
        logger.error("[connections.callback] token exchange failed: %s", exc)
        return _close_window_html(
            success=False,
            message="Failed to exchange authorization code with Google",
        )

    # Find the channel info
    try:
        channel = await youtube_oauth.get_connected_channel_info(
            tokens["access_token"]
        )
    except Exception as exc:
        logger.error("[connections.callback] channel lookup failed: %s", exc)
        return _close_window_html(
            success=False,
            message=f"Could not load channel info: {exc}",
        )

    # Upsert the SocialConnection row
    expires_at = youtube_oauth.compute_expires_at(tokens["expires_in"])

    # Check if a connection already exists for this user × platform
    existing_stmt = select(SocialConnection).where(
        SocialConnection.user_id == user_id,
        SocialConnection.platform == "youtube",
    )
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()

    if existing:
        # User reconnecting — update tokens
        existing.access_token_encrypted = encrypt_token(tokens["access_token"])
        if tokens.get("refresh_token"):
            existing.refresh_token_encrypted = encrypt_token(tokens["refresh_token"])
        existing.expires_at = expires_at
        existing.scopes = tokens.get("scope", "")
        existing.platform_user_id = channel["channel_id"]
        existing.handle = channel["handle"] or channel["title"]
        existing.sync_status = "idle"
        existing.last_error = None
    else:
        connection = SocialConnection(
            user_id=user_id,
            platform="youtube",
            platform_user_id=channel["channel_id"],
            handle=channel["handle"] or channel["title"],
            access_token_encrypted=encrypt_token(tokens["access_token"]),
            refresh_token_encrypted=(
                encrypt_token(tokens["refresh_token"])
                if tokens.get("refresh_token") else None
            ),
            expires_at=expires_at,
            scopes=tokens.get("scope", ""),
            sync_status="idle",
        )
        session.add(connection)

    await session.commit()
    logger.info(
        "[connections.callback] connected youtube for user=%s channel=%s",
        user_id, channel["channel_id"],
    )

    return _close_window_html(
        success=True,
        message=f"Connected to YouTube channel: {channel['title']}",
    )


# ─── Disconnect ────────────────────────────────────────────────

@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(
    connection_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Delete a connection. Cascades to snapshots and top_content."""
    stmt = select(SocialConnection).where(
        SocialConnection.id == connection_id,
        SocialConnection.user_id == current_user.id,
    )
    connection = (await session.execute(stmt)).scalar_one_or_none()

    if connection is None:
        raise HTTPException(404, "Connection not found")

    await session.delete(connection)
    await session.commit()


# ─── HTML response helper ──────────────────────────────────────

def _close_window_html(*, success: bool, message: str) -> HTMLResponse:
    """
    Render a small HTML page that closes itself or shows an error.

    Why HTML and not JSON?
        The browser navigates here directly via Google's redirect. JSON
        renders as ugly text. We return a styled page that either closes
        itself (success) or shows the error clearly.

    The `window.opener.postMessage` line lets the parent tab know the
    flow finished, so the frontend can refresh the connections list
    automatically. Optional but nice.
    """
    color = "#10b981" if success else "#ef4444"
    icon = "✓" if success else "✕"
    title = "Connected" if success else "Connection failed"

    return HTMLResponse(content=f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title} - Cupid</title>
  <style>
    body {{
      font-family: -apple-system, system-ui, sans-serif;
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; margin: 0; background: #fff9f3;
    }}
    .card {{
      background: white; padding: 40px; border-radius: 12px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
      text-align: center; max-width: 400px;
    }}
    .icon {{
      font-size: 48px; color: {color}; margin-bottom: 16px;
    }}
    h1 {{ margin: 0 0 12px; color: #2a3852; font-weight: 500; }}
    p {{ color: #7a8499; margin: 0; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">{icon}</div>
    <h1>{title}</h1>
    <p>{message}</p>
    {"<p style='margin-top:24px;font-size:13px'>You can close this window.</p>" if success else ""}
  </div>
  <script>
    // Notify parent window if opened as a popup
    if (window.opener) {{
      window.opener.postMessage(
        {{ type: 'oauth-result', platform: 'youtube', success: {str(success).lower()} }},
        '*'
      );
      {"setTimeout(() => window.close(), 1200);" if success else ""}
    }}
  </script>
</body>
</html>""")