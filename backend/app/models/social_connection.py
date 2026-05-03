"""
SocialConnection model — represents a user's authorized link to an
external platform (YouTube, future: LinkedIn, Instagram, etc).

═══════════════════════════════════════════════════════════════════════════
CONCEPT
═══════════════════════════════════════════════════════════════════════════
When a user clicks "Connect YouTube" and approves OAuth, we receive:
    - access_token   (short-lived, ~1 hour)
    - refresh_token  (long-lived, until user revokes)
    - the platform user ID (which YouTube channel)
    - granted scopes

We store all of that here, ONE row per (user × platform). If the same
user later connects Instagram, that's a second row.

═══════════════════════════════════════════════════════════════════════════
SECURITY: TOKEN ENCRYPTION
═══════════════════════════════════════════════════════════════════════════
Access and refresh tokens grant access to a user's social media data.
If the database is ever compromised, plaintext tokens become a credential
leak across every connected user.

We store tokens encrypted at rest using Fernet (symmetric encryption from
the `cryptography` library). The encryption key lives in an environment
variable, never in the database. An attacker who steals the DB but not
the env file gets a wall of garbage.

This is the standard "envelope encryption" pattern used everywhere from
Stripe to AWS Secrets Manager.
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime, ForeignKey, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.user import Base

if TYPE_CHECKING:
    from app.models.user import User


class SocialConnection(Base):
    __tablename__ = "social_connections"

    # ── Primary key ─────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Foreign key to user ─────────────────────────────────────
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Platform identification ─────────────────────────────────
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    # E.g. "youtube". Indexed via the composite unique constraint below.

    platform_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    # The YouTube channel ID (e.g. "UCxxxxx"). What identifies the user
    # on THEIR platform, not on ours. Useful for de-dup and API calls.

    handle: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Display name like "@CupidTestChannel". Shown in the UI. Optional —
    # not all platforms expose a clean handle.

    # ── OAuth tokens (encrypted) ────────────────────────────────
    # These columns store the OUTPUT of token_crypto.encrypt(token).
    # NEVER write a plaintext token here.
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    # Some platforms don't issue refresh tokens at all. Nullable for those.

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # When the access_token expires. We use this to know when to refresh
    # before making a YouTube API call.

    scopes: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    # Space-separated scope strings, e.g.
    # "https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/yt-analytics.readonly"
    # Useful for debugging "why doesn't this endpoint work" — often it's
    # because we asked for the wrong scope at OAuth time.

    # ── Sync metadata ───────────────────────────────────────────
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # Updated whenever the background sync job successfully fetches data.

    sync_status: Mapped[str] = mapped_column(
        String(16), default="idle", nullable=False,
    )
    # One of: 'idle', 'syncing', 'failed'. Surfaced in the UI so users
    # see "syncing..." vs "ready" vs "failed — reconnect".

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # If sync_status='failed', what went wrong. Helps support and debugging.

    # ── Relationships ───────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="social_connections")

    # ── Constraints ─────────────────────────────────────────────
    __table_args__ = (
        # A user can connect each platform exactly once. If they want to
        # change the connection, they disconnect first then reconnect.
        UniqueConstraint("user_id", "platform", name="uq_user_platform"),
    )

    def __repr__(self) -> str:
        return f"<SocialConnection {self.platform}:{self.handle or self.platform_user_id}>"