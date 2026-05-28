"""
app/earn/config.py
═══════════════════════════════════════════════════════════════════════════

Every tunable number for the Earn intelligence, in one place.

WHY A SEPARATE CONFIG FILE
──────────────────────────
The scoring logic (tiers.py, readiness.py) should read like *rules*, not
like a pile of magic numbers. When you later decide "actually, brand deals
should start at 8K not 5K for the Indian market", you want to change ONE
labelled constant here — not hunt through conditional logic. Separating the
"what the thresholds are" (this file) from "how they're applied" (tiers.py)
is the same discipline you'd use for any policy-vs-mechanism split.

Nothing here does work. It only declares values. That makes it safe to read,
safe to tune, and trivial to unit-test the logic that consumes it.
"""
from __future__ import annotations

from enum import Enum


# ─────────────────────────────────────────────────────────────────────────
#  Audience tiers
# ─────────────────────────────────────────────────────────────────────────

class Tier(str, Enum):
    """
    The four creator-economy bands, by total followers summed across all
    connected platforms. Inheriting from str makes these JSON-serializable
    and DB-friendly with zero conversion code.
    """
    NANO = "nano"      # foundation: start earning anything, build the habit
    MICRO = "micro"    # activation: first real income unlocks
    MID = "mid"        # serious: brand deals & recurring streams are real money
    MACRO = "macro"    # premium: the full menu, including partnerships & licensing


# Ordered low → high. Flexing up/down means stepping along this tuple, so the
# ORDER here is the source of truth for "which tier is bigger". Never reorder
# without understanding that flex logic depends on the index.
TIER_ORDER: tuple[Tier, ...] = (Tier.NANO, Tier.MICRO, Tier.MID, Tier.MACRO)


# The lower follower bound of each tier. A creator is in the highest tier
# whose threshold they meet or exceed. These are the numbers you'll tune most
# often as you learn your market — they live here precisely so that's a
# one-line edit.
TIER_FLOORS: dict[Tier, int] = {
    Tier.NANO: 0,
    Tier.MICRO: 1_000,
    Tier.MID: 10_000,
    Tier.MACRO: 100_000,
}


# Human-facing one-liners describing each tier — used by the coach narrative
# and the Section 1 tier badge. Honest about where the creator stands.
TIER_BLURB: dict[Tier, str] = {
    Tier.NANO:  "You're building your foundation. The goal now is to start earning *something* and build momentum.",
    Tier.MICRO: "You've hit activation. Your first real income streams are genuinely within reach.",
    Tier.MID:   "You're at serious scale. Brand partnerships and recurring revenue are real money for you now.",
    Tier.MACRO: "You're in premium territory. The full monetization menu is open, including high-value partnerships.",
}


# ─────────────────────────────────────────────────────────────────────────
#  Engagement flex
# ─────────────────────────────────────────────────────────────────────────
# Raw follower count is a blunt instrument. A 5K account pulling 20K monthly
# views is punching above its weight; a dormant 15K account pulling 1K views
# is not really "mid tier" in any way a brand would respect. So we let the
# tier flex by AT MOST one step, based on an engagement signal we can compute
# from the data we actually have (no revenue, no private metrics).
#
# The signal: engagement_ratio = monthly_views / total_followers
#   • A ratio well above 1.0 means reach exceeds audience size → algorithmic
#     tailwind, virality, punchy content → justify flexing UP.
#   • A ratio well below 1.0 means the audience isn't watching → dormant →
#     flex DOWN so we don't hand out advice they can't yet act on.
#
# Flex is deliberately conservative: one step, with guards, so a single viral
# fluke can't catapult a 200-follower account into "mid tier".

# Getting this many times your follower count in monthly views → flex up.
FLEX_UP_RATIO: float = 3.0

# Getting this small a fraction of your follower count in views → flex down.
FLEX_DOWN_RATIO: float = 0.2

# Guard: need a real posting history before an up-flex is credible. Protects
# against the "one lucky video" case where views spike but there's no
# sustained body of work a brand would actually evaluate.
MIN_POSTS_TO_FLEX_UP: int = 5

# Guard: below this follower count the ratio is statistical noise (a brand-new
# account with 20 followers and one 200-view post has ratio 10.0, meaningless).
# Don't flex either direction below this floor.
MIN_FOLLOWERS_FOR_RATIO: int = 50


# ─────────────────────────────────────────────────────────────────────────
#  Confidence
# ─────────────────────────────────────────────────────────────────────────
# We're transparent about how much we trust our own read. The coach softens
# its language when confidence is low ("based on the limited data we have…").

# At or above this many connected platforms' worth of data, and enough
# followers, we call it high confidence.
MIN_FOLLOWERS_FOR_CONFIDENCE: int = 100