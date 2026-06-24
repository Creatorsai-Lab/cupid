"""
app/subscriptions/service.py
═══════════════════════════════════════════════════════════════════════════

The ONE module that writes to the subscriptions table. Everything else reads.

WHY THE WRITE PATH IS CENTRALIZED
─────────────────────────────────
A subscription is the kind of state that, if updated from many places, drifts
into impossible combinations: tier says "pro" but status says "incomplete",
or cancel_at_period_end is true but the row got recreated, etc.

By funneling every write through this file, we get:
  - One place to add validation (no typoed tier values getting into the DB)
  - One place to add audit logging when we need it
  - One place where Stripe webhooks plug in (replacing manual admin calls
    with provider-driven calls — same function signature)
  - Idempotency guarantees: ensure_subscription is safe to call repeatedly

If you find yourself wanting to UPDATE a subscriptions row from another file,
the right move is to add a function HERE and call it from there.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.subscriptions.constants import (
    DEFAULT_TIER_FOR_NEW_USERS,
    STATUS_ACTIVE,
    is_valid_status,
    is_valid_tier,
)
from app.subscriptions.models import Subscription

logger = logging.getLogger("app.subscriptions.service")


# ─────────────────────────────────────────────────────────────────────────
#  Reads (kept here so writes and their adjacent reads live together)
# ─────────────────────────────────────────────────────────────────────────


async def get_subscription(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> Subscription | None:
    """Lookup by user. Returns None if no row exists (rare; see ensure_subscription)."""
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    return result.scalar_one_or_none()


# ─────────────────────────────────────────────────────────────────────────
#  Writes
# ─────────────────────────────────────────────────────────────────────────


async def ensure_subscription(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> Subscription:
    """
    Idempotently guarantee that this user has a subscription row.

    Called on every login (and during the auth-dep that backs TierContext)
    to keep the invariant "every user has exactly one subscription row".
    Safe to call repeatedly — if the row exists, returns it; otherwise
    creates one with the default tier.

    This guarantee is what lets the entitlement resolver never handle a
    "missing subscription" case — the row is always there.
    """
    existing = await get_subscription(session, user_id)
    if existing is not None:
        return existing

    sub = Subscription(
        user_id=user_id,
        tier=DEFAULT_TIER_FOR_NEW_USERS,
        status=STATUS_ACTIVE,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    logger.info(
        "[subscriptions] created default subscription for user=%s tier=%s",
        user_id,
        DEFAULT_TIER_FOR_NEW_USERS,
    )
    return sub


async def set_user_tier(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    tier: str,
    status: str = STATUS_ACTIVE,
    current_period_end: datetime | None = None,
    cancel_at_period_end: bool = False,
    grandfathered_until: datetime | None = None,
    provider: str | None = None,
    provider_customer_id: str | None = None,
    provider_subscription_id: str | None = None,
    reason: str = "manual",
    actor_id: uuid.UUID | None = None,
    actor_email: str | None = None,
) -> Subscription:
    """
    THE write-path. Sets a user's tier with full billing context.

    Used by:
      - The admin endpoint (manual control during v1)
      - Stripe webhooks (in v2, replacing the manual calls)
      - The signup flow (one call to set the default after user creation)

    `reason` is a free-text tag that goes into the log for forensics. When
    we later add an audit table, this is what gets recorded.

    Rejects invalid tier/status strings loudly — typos die here, not in
    production reads.
    """
    if not is_valid_tier(tier):
        raise ValueError(f"Invalid tier: {tier!r}")
    if not is_valid_status(status):
        raise ValueError(f"Invalid status: {status!r}")

    sub = await ensure_subscription(session, user_id)

    prev_tier = sub.tier
    sub.tier = tier
    sub.status = status
    sub.current_period_end = current_period_end
    sub.cancel_at_period_end = cancel_at_period_end
    sub.grandfathered_until = grandfathered_until
    if provider is not None:
        sub.provider = provider
    if provider_customer_id is not None:
        sub.provider_customer_id = provider_customer_id
    if provider_subscription_id is not None:
        sub.provider_subscription_id = provider_subscription_id

    # Append-only audit trail — recorded in the SAME transaction as the change,
    # so a tier change and its audit row commit together (or not at all).
    session.add(
        AuditLog(
            actor_id=actor_id,
            actor_email=actor_email,
            action="tier.set",
            target_type="user",
            target_id=str(user_id),
            detail={
                "from_tier": prev_tier,
                "to_tier": tier,
                "status": status,
                "reason": reason,
            },
        )
    )

    await session.commit()
    await session.refresh(sub)

    logger.info(
        "[subscriptions] tier changed user=%s %s → %s status=%s reason=%s",
        user_id,
        prev_tier,
        tier,
        status,
        reason,
    )
    return sub


async def schedule_cancellation_at_period_end(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> Subscription:
    """
    Mark the subscription to drop at period_end without immediate access loss.

    Standard SaaS pattern — user clicks "cancel", keeps their tier until the
    period they already paid for ends, then drops. The entitlement resolver
    reads cancel_at_period_end and shows "your plan ends on X" in the UI.

    Actual tier change happens when Stripe (in v2) fires
    customer.subscription.deleted at period end and a webhook calls
    set_user_tier(tier=TIER_FREE).
    """
    sub = await ensure_subscription(session, user_id)
    sub.cancel_at_period_end = True
    await session.commit()
    await session.refresh(sub)
    logger.info("[subscriptions] cancellation scheduled user=%s", user_id)
    return sub
