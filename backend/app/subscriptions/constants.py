"""
app/subscriptions/constants.py
═══════════════════════════════════════════════════════════════════════════

The stable vocabulary of the subscription system. Every other file in this
package — and any feature that gates on tier — imports its tier IDs and
status values from HERE.

WHY THIS IS ITS OWN FILE
────────────────────────
Three reasons, all about preventing future pain:

  1. ONE SOURCE OF TRUTH. A typo like `"premiun"` somewhere else in the
     codebase becomes a runtime bug that silently denies a user access.
     By importing TIER_PREMIUM, a typo becomes an ImportError at module
     load — caught immediately, never deployed.

  2. RENAME-PROOF. When marketing renames "Creator" to "Maker" next year,
     you change ONE STRING in TIER_DISPLAY_NAME. The database value stays
     `"pro"`. No migration. This separation of internal-id from display-name
     is the single most important architectural decision in this package.

  3. STRIPE-READY. The status values (`active`, `past_due`, `canceled`,
     `incomplete`) match Stripe's vocabulary exactly. When Stripe is wired
     in for v2, webhook handlers can write the status string directly with
     no translation layer.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────
#  TIER IDENTIFIERS — internal, lowercase, stable forever
# ─────────────────────────────────────────────────────────────────────────
# These strings live in the database. Treat them as constants you can never
# change without a migration. The marketing names are completely separate.

TIER_FREE = "free"
TIER_PRO = "pro"
TIER_PREMIUM = "premium"

TIERS: tuple[str, ...] = (TIER_FREE, TIER_PRO, TIER_PREMIUM)

# Numeric rank for tier comparisons (`if ctx.tier_rank >= TIER_RANK[TIER_PRO]`).
# Encoding the order here means callers never need to know it; they ask the
# constant. If we add an Enterprise tier later, it goes at the end with rank 3.
TIER_RANK: dict[str, int] = {
    TIER_FREE: 0,
    TIER_PRO: 1,
    TIER_PREMIUM: 2,
}


# ─────────────────────────────────────────────────────────────────────────
#  DISPLAY NAMES — the UI layer, the only place marketing copy lives
# ─────────────────────────────────────────────────────────────────────────
# Rename freely. The database doesn't care.

TIER_DISPLAY_NAME: dict[str, str] = {
    TIER_FREE: "Hustler",
    TIER_PRO: "Creator",
    TIER_PREMIUM: "Influencer",
}


# ─────────────────────────────────────────────────────────────────────────
#  STATUS — mirrors Stripe's subscription status vocabulary
# ─────────────────────────────────────────────────────────────────────────
# Even though Stripe isn't wired in yet, we use Stripe's status words from
# day one. When webhooks arrive in v2, they write these strings directly.

STATUS_ACTIVE = "active"  # subscription is current; full access
STATUS_PAST_DUE = "past_due"  # payment failed, Stripe retrying — grace period
STATUS_CANCELED = "canceled"  # ended; access depends on period_end
STATUS_INCOMPLETE = "incomplete"  # signup not finished (e.g. 3DS auth pending)

STATUSES: tuple[str, ...] = (
    STATUS_ACTIVE,
    STATUS_PAST_DUE,
    STATUS_CANCELED,
    STATUS_INCOMPLETE,
)


# ─────────────────────────────────────────────────────────────────────────
#  LAUNCH BEHAVIOR — the one knob to flip for v2
# ─────────────────────────────────────────────────────────────────────────
# Every new signup currently gets this tier. At v2 launch, change this to
# TIER_FREE and the entire tier system "wakes up" — gates start firing for
# new users without any other code change.

DEFAULT_TIER_FOR_NEW_USERS: str = TIER_PRO


def is_valid_tier(tier: str) -> bool:
    """Used by admin endpoint + Pydantic validators to reject typos."""
    return tier in TIER_RANK


def is_valid_status(status: str) -> bool:
    return status in STATUSES
