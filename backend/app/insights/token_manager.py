r"""
Token Manager — decrypt stored tokens and refresh them when expired.

1. THE CORE PROBLEM
-----------------
Access tokens from Google live ~1 hour. Our background sync runs every
6 hours. So 5 out of 6 sync attempts will find an expired access token
and need to refresh it before making any YouTube API call.

Without a refresh layer, every sync would fail. With one, sync works
indefinitely (until the user explicitly revokes access in their Google
account settings).

2. THE PATTERN: CHECK BEFORE USE
-----------------------------
Every API call goes through `get_valid_access_token(connection)`:
    1. Read connection.expires_at
    2. If it's in the past (or within 60s of expiry), refresh now
    3. Otherwise return the decrypted current token

The 60-second buffer prevents race conditions: imagine the token expires
exactly when we make the API call. By refreshing 60 seconds early, we
always have a fresh token in hand when the API call goes out.

3. TRANSFERABLE PATTERN
-----------------------
This exact code shape works for ANY OAuth 2.0 integration: Slack, Notion,
GitHub, Stripe Connect, Discord. The only thing that changes is which
token endpoint you POST to. Worth internalizing this pattern — it's
universal.

"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.connections import youtube_oauth
from app.connections.token_crypto import decrypt_token, encrypt_token
from app.models.social_connection import SocialConnection

logger = logging.getLogger(__name__)

# Refresh this many seconds BEFORE the actual expiry, to dodge race conditions
EXPIRY_BUFFER_SECONDS = 60


class TokenRefreshFailed(Exception):
    """User has revoked access or refresh_token is invalid. Reconnect needed."""


async def get_valid_access_token(
    connection: SocialConnection,
    session: AsyncSession,
) -> str:
    """
    Return a valid (decrypted, unexpired) access token for this connection.

    If the stored access token is expired or about to be, refresh it
    using the refresh_token, persist the new tokens to the DB, and
    return the new access token.

    Raises:
        TokenRefreshFailed: refresh_token is no longer valid. The
            calling code should mark the connection as failed and
            prompt the user to reconnect.
    """
    if not _needs_refresh(connection):
        return decrypt_token(connection.access_token_encrypted)

    if not connection.refresh_token_encrypted:
        # No refresh token stored — happens if the original OAuth flow
        # didn't include access_type=offline. Can't refresh, must reconnect.
        raise TokenRefreshFailed(
            "No refresh_token stored. User must reconnect their account."
        )

    refresh_token = decrypt_token(connection.refresh_token_encrypted)
    logger.info(
        "[token_manager] refreshing access token for connection %s",
        connection.id,
    )

    try:
        new_tokens = await youtube_oauth.refresh_access_token(refresh_token)
    except RuntimeError as exc:
        # Google returned 400 → refresh_token revoked or invalid
        raise TokenRefreshFailed(str(exc)) from exc

    # Persist new tokens
    connection.access_token_encrypted = encrypt_token(new_tokens["access_token"])
    connection.expires_at = youtube_oauth.compute_expires_at(
        new_tokens["expires_in"]
    )
    # Google sometimes returns a new refresh_token, sometimes doesn't.
    # If it does, update; otherwise keep the existing one.
    if new_tokens.get("refresh_token"):
        connection.refresh_token_encrypted = encrypt_token(
            new_tokens["refresh_token"]
        )

    await session.commit()
    logger.info(
        "[token_manager] refreshed; new expiry %s",
        connection.expires_at.isoformat() if connection.expires_at else None,
    )

    return new_tokens["access_token"]


def _needs_refresh(connection: SocialConnection) -> bool:
    """True if the stored access token is expired or close to expiring."""
    if not connection.expires_at:
        return True
    now_utc = datetime.now(timezone.utc)
    threshold = now_utc + timedelta(seconds=EXPIRY_BUFFER_SECONDS)
    return connection.expires_at <= threshold