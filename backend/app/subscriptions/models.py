"""
app/subscriptions/models.py
═══════════════════════════════════════════════════════════════════════════

The Subscription table — exactly one row per user, always. The mere existence
of the row guarantees the entitlement resolver never has to handle a "missing
subscription" edge case; every user has an entitlement, period.

WHY ONE-ROW-PER-USER (NOT ONE-PER-PURCHASE)
───────────────────────────────────────────
At v1 the system tracks the user's *current state*, not a history of every
plan change. Free users get a row with `tier="free", provider=null`. Paid
users get the same row updated in place. This is simpler than an event log
and entirely adequate for our needs — Stripe itself keeps the full billing
history; we just mirror the current state for fast read access.

If we later need an audit trail of plan changes, that's a separate `plan_events`
table, not a redesign of this one.

WHY STRIPE COLUMNS EXIST EVEN THOUGH STRIPE ISN'T WIRED IN
──────────────────────────────────────────────────────────
Building the empty columns now means v2 webhook integration is purely a write
into existing fields — no schema migration, no risky reshape. They sit at
null today. The cost of having unused columns is negligible; the cost of
adding them under load later is real.

NO BACK-REFERENCE TO User
─────────────────────────
The Subscription has a FK to users.id but does NOT add a relationship on the
User model — matching the discipline used for the earn and history features.
This keeps the package fully self-contained; nothing outside subscriptions/
needs to know this table exists at the ORM level.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base
from app.subscriptions.constants import (
    STATUS_ACTIVE,
    TIER_PRO,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # One subscription per user, enforced by unique=True. The DB will refuse
    # duplicates if a service-layer bug ever tries to create two rows.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # The tier and status vocabulary. Kept as String (not a DB enum) so adding
    # a new tier later doesn't require an enum-type migration — just a code
    # change. Validation happens at the service layer via constants.is_valid_*.
    tier: Mapped[str] = mapped_column(String(16), nullable=False, default=TIER_PRO)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=STATUS_ACTIVE
    )

    # ── Stripe integration columns — nullable for now, populated in v2 ──
    # Existence checked: `provider is None` means "no billing provider yet"
    # (current launch state), which the entitlement resolver treats as
    # "this user's tier was set manually or by the default-tier rule".
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )

    # When the current billing period ends. Nullable because pre-Stripe users
    # have no period. The resolver uses this to decide "they canceled but it's
    # still paid through X" vs "their cancellation is effective now".
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # True after the user clicks "cancel" but before period_end arrives.
    # Surfaced in the UI so they know their plan is winding down without
    # immediately losing access.
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # ── Grandfather window for v1→v2 transition ─────────────────────────
    # When v2 launches and the default flips to Free, existing users get
    # this date set to (v2_launch_date + 7 days). The resolver checks it and
    # keeps them on Pro for the grace period, then they drop to Free
    # automatically — no scheduled job, no migration, just a read-time check.
    grandfathered_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
