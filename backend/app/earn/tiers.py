"""
app/earn/tiers.py
═══════════════════════════════════════════════════════════════════════════

Turn the three audience numbers (followers, monthly views, posts) into a
creator tier — WITH its reasoning attached.

PURE FUNCTIONS, NO I/O
──────────────────────
Nothing in this file touches the database, the network, or the clock. It
takes numbers in and returns a verdict. That is a deliberate architectural
choice, and the same one you made for quality_scorer.py:

  • It runs in microseconds, so it's free to call as often as we like.
  • It's trivially unit-testable — feed numbers, assert the tier, no mocks,
    no fixtures, no async event loop.
  • It's reproducible — the same inputs ALWAYS give the same output, which is
    exactly what you want for advice a user might revisit and expect to be
    stable.

The rule of thumb: keep the *decisions* deterministic and here; push the
*data gathering* (signals.py) and the *expression* (coach.py) to the edges.

WHY RETURN A RICH OBJECT, NOT JUST A TIER
─────────────────────────────────────────
We could return just `Tier.MICRO`. We don't, because the *why* is gold for
the coach. "You're Micro tier, but your views run 3x your follower count —
you're punching above your weight, so let's be a little more ambitious" is a
genuinely great coaching line, and it falls straight out of the flex logic.
Throwing that reasoning away and re-deriving it later would be wasteful and
error-prone. Compute once, carry the explanation.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.earn.config import (
    FLEX_DOWN_RATIO,
    FLEX_UP_RATIO,
    MIN_FOLLOWERS_FOR_CONFIDENCE,
    MIN_FOLLOWERS_FOR_RATIO,
    MIN_POSTS_TO_FLEX_UP,
    TIER_FLOORS,
    TIER_ORDER,
    Tier,
)


# ─────────────────────────────────────────────────────────────────────────
#  Inputs and outputs
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AudienceSignals:
    """
    The raw material, gathered by signals.py from connected accounts.

    These are the ONLY inputs to the whole eligibility engine — no revenue,
    no private analytics, nothing that raises a privacy trade-off. Just the
    public-facing scale of the creator's presence, summed across whatever
    platforms they've connected.
    """
    total_followers: int          # summed across all connected platforms
    monthly_views: int            # summed; 0 if unknown
    total_posts: int              # summed; 0 if unknown
    connected_platforms: int      # how many platforms contributed (for confidence)
    has_data: bool                # False if we couldn't read any real signal

    @staticmethod
    def empty() -> "AudienceSignals":
        """A creator with nothing connected / no data yet."""
        return AudienceSignals(
            total_followers=0,
            monthly_views=0,
            total_posts=0,
            connected_platforms=0,
            has_data=False,
        )


@dataclass(frozen=True)
class TierAssessment:
    """The verdict, with its reasoning fully exposed for the coach to use."""
    tier: Tier                    # final tier, after any flex
    base_tier: Tier               # tier from raw followers, before flex
    flex: int                     # -1, 0, or +1 — how engagement adjusted it
    flex_reason: str | None       # human-readable explanation, or None if no flex
    engagement_ratio: float | None  # monthly_views / followers, or None if not computable
    confidence: str               # "high" | "low" — how much we trust this read
    signals: AudienceSignals      # carried through so callers don't re-fetch


# ─────────────────────────────────────────────────────────────────────────
#  The core computation
# ─────────────────────────────────────────────────────────────────────────

def _base_tier_from_followers(followers: int) -> Tier:
    """
    The highest tier whose follower floor the creator meets or exceeds.

    Walk tiers from highest to lowest and return the first one they clear.
    Iterating high→low means the first match is always the correct (highest)
    tier, so we can return immediately.
    """
    for tier in reversed(TIER_ORDER):
        if followers >= TIER_FLOORS[tier]:
            return tier
    return Tier.NANO  # unreachable (NANO floor is 0) but explicit for safety


def _step(tier: Tier, delta: int) -> Tier:
    """
    Move `delta` steps along TIER_ORDER, clamped to the ends.

    Clamping (rather than wrapping or erroring) means an up-flex on a MACRO
    creator simply stays MACRO, and a down-flex on a NANO stays NANO — the
    natural, correct behavior at the boundaries.
    """
    idx = TIER_ORDER.index(tier)
    new_idx = max(0, min(len(TIER_ORDER) - 1, idx + delta))
    return TIER_ORDER[new_idx]


def assess_tier(signals: AudienceSignals) -> TierAssessment:
    """
    The single public entry point: signals → tier assessment.

    Steps:
      1. Base tier from raw follower count.
      2. Compute the engagement ratio, if it's meaningful to do so.
      3. Decide a flex (±1) from that ratio, behind guards.
      4. Apply the flex, clamped to tier bounds.
      5. Attach confidence and a human-readable reason.
    """
    # ── 1. Base tier ─────────────────────────────────────────────────────
    base = _base_tier_from_followers(signals.total_followers)

    # ── 2. Engagement ratio (only when it's not noise) ───────────────────
    ratio: float | None = None
    if signals.has_data and signals.total_followers >= MIN_FOLLOWERS_FOR_RATIO:
        # monthly_views can legitimately be 0 (unknown / not provided); that
        # yields ratio 0.0, which correctly reads as "dormant" below.
        ratio = signals.monthly_views / signals.total_followers

    # ── 3 & 4. Decide and apply flex ─────────────────────────────────────
    flex = 0
    flex_reason: str | None = None

    if ratio is not None:
        if ratio >= FLEX_UP_RATIO and signals.total_posts >= MIN_POSTS_TO_FLEX_UP:
            # Punching above their follower count, with a real body of work.
            flexed = _step(base, +1)
            if flexed != base:  # only call it a flex if the tier actually moved
                flex = 1
                flex_reason = (
                    f"Your content pulls about {ratio:.1f}x your follower count in monthly "
                    f"views — you're punching above your size, so we're being a little more ambitious."
                )
        elif ratio <= FLEX_DOWN_RATIO:
            # Audience present but not engaging — don't over-promise.
            flexed = _step(base, -1)
            if flexed != base:
                flex = -1
                flex_reason = (
                    "Your monthly views are low relative to your following right now, so we're "
                    "focusing on streams that work even while you re-engage your audience."
                )

    final = _step(base, flex)

    # ── 5. Confidence ────────────────────────────────────────────────────
    # Low confidence when we have no data, no connected platforms, or so few
    # followers that any read is shaky. The coach uses this to soften language.
    if (
        not signals.has_data
        or signals.connected_platforms == 0
        or signals.total_followers < MIN_FOLLOWERS_FOR_CONFIDENCE
    ):
        confidence = "low"
    else:
        confidence = "high"

    return TierAssessment(
        tier=final,
        base_tier=base,
        flex=flex,
        flex_reason=flex_reason,
        engagement_ratio=ratio,
        confidence=confidence,
        signals=signals,
    )