"""
app/subscriptions/entitlement.py
═══════════════════════════════════════════════════════════════════════════

The resolver that turns billing state into entitlement state.

THE TWO STATE MACHINES, RECONCILED
──────────────────────────────────
Stripe (and our `subscriptions` table that mirrors it) tracks BILLING STATE:
status, tier, period_end, etc. This is the raw truth of what the user has
purchased and where they are in the billing cycle.

The rest of the app needs ENTITLEMENT STATE: "right now, what is this user
allowed to do?" — a single, clean answer.

The mapping between them is NOT trivial. A user who canceled but is still
inside their paid period should have full access. A user in `past_due`
should have access AND a banner. A user who's been grandfathered through a
v2 transition should temporarily get a higher tier than their billing row
says. THIS file is the only place that knows how to translate.

WHY THIS LIVES AT READ TIME (NOT IN A SCHEDULED JOB)
────────────────────────────────────────────────────
You could write a cron job that runs nightly and "downgrades expired users".
We don't, because:

  - It would introduce a window where billing and entitlement disagree.
  - It's another moving part to monitor.
  - It's strictly less correct: resolving on every read is always up-to-date
    within milliseconds.

The cost of read-time resolution is one tiny pure function per request.
Cheap. Always right. No scheduling.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.subscriptions.constants import (
    STATUS_CANCELED,
    STATUS_INCOMPLETE,
    STATUS_PAST_DUE,
    TIER_DISPLAY_NAME,
    TIER_FREE,
    TIER_PREMIUM,
    TIER_PRO,
    TIER_RANK,
)
from app.subscriptions.models import Subscription
from app.subscriptions.policy import policy_summary

# ─────────────────────────────────────────────────────────────────────────
#  The resolved entitlement — what every tier-aware code path consumes
# ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TierContext:
    """
    The single immutable object that flows through every tier-aware request.
    Frozen so middleware/handlers can't accidentally mutate it (e.g. "upgrade
    this user for one request") — any tier change goes through service.py.
    """

    user_id: uuid.UUID

    # The effective tier — AFTER grandfather, grace, and cancellation logic.
    # This is what every downstream check should read, never the raw `tier`
    # field from the database.
    tier: str
    tier_rank: int  # for `if ctx.tier_rank >= TIER_RANK[TIER_PRO]`
    display_name: str  # marketing-friendly: "Creator"

    # Raw status from billing — surfaced so UI can show "your card failed"
    status: str
    payment_warning: bool  # True when status == past_due

    # Timing windows — for UI messages like "your plan ends on Dec 12"
    period_end: datetime | None
    grandfathered_until: datetime | None
    cancel_at_period_end: bool

    # The capability matrix for this tier (from policy.policy_summary)
    limits: dict

    # UI hint: should the frontend render "locked" overlays on higher-tier features?
    # True for anyone below the top tier.
    show_locked_features: bool


# ─────────────────────────────────────────────────────────────────────────
#  The resolver — the only function with the business rules
# ─────────────────────────────────────────────────────────────────────────


def resolve_entitlement(
    sub: Subscription,
    now: datetime | None = None,
) -> TierContext:
    """
    Translate a raw Subscription row into the user's current entitlement.

    Pure function: same inputs always produce the same output. `now` is
    optional purely so tests can pin time; production always uses real time.
    """
    if now is None:
        now = datetime.now(UTC)

    # The raw tier from the row — what billing thinks they have.
    effective_tier = sub.tier
    payment_warning = False

    # ── Rule 1: Grandfather window ─────────────────────────────────────
    # If the user is in a v1→v2 grace period, give them Pro regardless of
    # what their billing row says. (Handles "you were on Pro by default,
    # now we've launched Free — here's a 7-day buffer.")
    if sub.grandfathered_until and sub.grandfathered_until > now:
        # Grandfather only matters when it gives them MORE than they have.
        # If they're already on Premium, leave them on Premium.
        if TIER_RANK.get(effective_tier, 0) < TIER_RANK[TIER_PRO]:
            effective_tier = TIER_PRO

    # ── Rule 2: Status interpretation ──────────────────────────────────
    if sub.status == STATUS_PAST_DUE:
        # Payment failed but Stripe is retrying. Keep access; flag the UI.
        # This is the grace window — typical SaaS norm is a few days before
        # transitioning to canceled.
        payment_warning = True

    elif sub.status == STATUS_CANCELED:
        # They've ended billing. Two sub-cases:
        if sub.current_period_end and sub.current_period_end > now:
            # They canceled mid-period; still paid through period_end.
            # Keep their tier; UI will show "your plan ends on X" via
            # cancel_at_period_end + period_end fields.
            pass
        else:
            # Period over (or no period was set). Drop to free.
            effective_tier = TIER_FREE

    elif sub.status == STATUS_INCOMPLETE:
        # Payment flow not completed (e.g. waiting on 3DS auth). No paid
        # access until they finish. Safer to assume free until status flips.
        effective_tier = TIER_FREE

    # status == STATUS_ACTIVE → no adjustments; tier stands.

    # ── Build the immutable context ────────────────────────────────────
    return TierContext(
        user_id=sub.user_id,
        tier=effective_tier,
        tier_rank=TIER_RANK[effective_tier],
        display_name=TIER_DISPLAY_NAME[effective_tier],
        status=sub.status,
        payment_warning=payment_warning,
        period_end=sub.current_period_end,
        grandfathered_until=sub.grandfathered_until,
        cancel_at_period_end=sub.cancel_at_period_end,
        limits=policy_summary(effective_tier),
        # Show locks for anyone not on the top tier so they discover what
        # premium offers. Frontend may choose to suppress these during the
        # v1 launch when no upgrade path exists yet.
        show_locked_features=effective_tier != TIER_PREMIUM,
    )
