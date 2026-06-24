"""
app/subscriptions/policy.py
═══════════════════════════════════════════════════════════════════════════

The full tier policy matrix, encoded as pure functions. This file is the
EXECUTABLE VERSION of the tier comparison table you (Adya) drafted.

WHY THIS FILE EXISTS, AND WHY IT MATTERS
────────────────────────────────────────
Every feature in Cupid that varies by tier reads from THIS file. Not from
inline conditionals scattered through routers and services — from here.

That centralization is what makes the system maintainable. The moment you
write `if tier == "pro": limit = 5` inside a router, your tier rules are
fragmented across the codebase. Next time you change pricing, you're hunting
through twenty files. Keep every decision here, and a pricing change is one
diff against one file.

Two design rules to maintain forever:
  1. POLICY FUNCTIONS ARE PURE. No I/O, no DB, no logging. They take a tier
     string in and return a value out. This makes them trivially testable
     and impossible to break in subtle ways.
  2. EVERY GATE READS THROUGH A NAMED FUNCTION. Routers/services never check
     `if tier == "free"` directly. They call `policy.can_access_earn(tier)`.
     The names ARE the business rules; reading the call sites in the rest of
     the codebase reads like a feature specification.
"""

from __future__ import annotations

from app.subscriptions.constants import (
    TIER_FREE,
    TIER_PREMIUM,
    TIER_PRO,
)

# ─────────────────────────────────────────────────────────────────────────
#  Content creation gates
# ─────────────────────────────────────────────────────────────────────────


def posts_per_day(tier: str) -> int:
    """
    How many post generations the user can run per 24-hour window.
    Returns a very large number for unlimited tiers so callers can compare
    against a count without needing to special-case None.
    """
    return {
        TIER_FREE: 1,
        TIER_PRO: 5,
        TIER_PREMIUM: 999_999,  # effectively unlimited
    }[tier]


def can_create_video_posts(tier: str) -> bool:
    """Free tier can create all content types except video posts."""
    return tier != TIER_FREE


# ─────────────────────────────────────────────────────────────────────────
#  Page / feature access gates
# ─────────────────────────────────────────────────────────────────────────


def can_access_earn(tier: str) -> bool:
    """Earn page (monetization coach) is paid-only."""
    return tier != TIER_FREE


def can_view_trends(tier: str) -> bool:
    """All tiers can view the trends page itself."""
    return True


def can_refresh_trends(tier: str) -> bool:
    """Only paid tiers can hit the manual refresh button."""
    return tier != TIER_FREE


def can_use_trends_post_tab(tier: str) -> bool:
    """The 'create post from this trend' tab is paid-only."""
    return tier != TIER_FREE


# ─────────────────────────────────────────────────────────────────────────
#  Connections gates
# ─────────────────────────────────────────────────────────────────────────


def max_social_profiles(tier: str) -> int | None:
    """
    Total number of social profiles a user can connect.
    None == unlimited; callers treat None as "no cap to enforce".
    """
    return {
        TIER_FREE: 1,
        TIER_PRO: None,
        TIER_PREMIUM: None,
    }[tier]


def can_connect_multiple_same_platform(tier: str) -> bool:
    """
    Premium-only: e.g. two Instagram accounts on one Cupid account.
    Useful for creators who run multiple personas.
    """
    return tier == TIER_PREMIUM


# ─────────────────────────────────────────────────────────────────────────
#  History / retention
# ─────────────────────────────────────────────────────────────────────────


def history_retention_days(tier: str) -> int:
    """
    How far back the user can see their generated post history.
    Identical across all tiers in v1; keeping the function shape so we can
    differentiate later without touching call sites.
    """
    return 14


# ─────────────────────────────────────────────────────────────────────────
#  Assistant (Cia) customization
# ─────────────────────────────────────────────────────────────────────────


def can_customize_assistant(tier: str) -> bool:
    """
    Premium-tier perk: rename Cia, change her character, etc.
    Not implemented in v1 but the gate exists so the feature can be added
    without touching the surrounding code.
    """
    return tier == TIER_PREMIUM


# ─────────────────────────────────────────────────────────────────────────
#  Queue / priority — server-trusted tags on background tasks
# ─────────────────────────────────────────────────────────────────────────


def priority_class(tier: str) -> str:
    """
    The priority label attached to background tasks (agent runs, discovery
    jobs). Today's asyncio pipeline doesn't act on this yet — but tagging
    it now means the day we move to Celery/Redis-queue, priority routing
    is a worker-side change, not a tier-system change.
    """
    return {
        TIER_FREE: "standard",
        TIER_PRO: "high",
        TIER_PREMIUM: "dedicated",
    }[tier]


# ─────────────────────────────────────────────────────────────────────────
#  Summary — what the /entitlement endpoint serializes to the frontend
# ─────────────────────────────────────────────────────────────────────────


def policy_summary(tier: str) -> dict:
    """
    The complete read-only view of this tier's capabilities. The frontend
    receives this object once at login and reads from it to decide what to
    render (and what to render as locked).

    Keep this dict's KEYS stable — the frontend reads them by name. Adding
    new keys is safe; renaming or removing breaks the UI.
    """
    return {
        "posts_per_day": posts_per_day(tier),
        "video_posts": can_create_video_posts(tier),
        "earn_access": can_access_earn(tier),
        "trends_view": can_view_trends(tier),
        "trends_refresh": can_refresh_trends(tier),
        "trends_post_tab": can_use_trends_post_tab(tier),
        "max_social_profiles": max_social_profiles(tier),
        "multi_same_platform": can_connect_multiple_same_platform(tier),
        "history_retention_days": history_retention_days(tier),
        "assistant_customization": can_customize_assistant(tier),
        "priority": priority_class(tier),
    }
