"""
app/earn/service.py
═══════════════════════════════════════════════════════════════════════════

The orchestration layer. The router stays thin; this is where the pipeline
runs:

    signals → tier assessment → readiness report → (opportunities ‖ coach)
            → assembled four-section ReadinessResponse

Also owns the profile read/write (the Q&A gate) and the niche normalization
used for matching and creative ideas.

Thin-router / fat-service, the same split you used for history and insights.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.earn import coach
from app.earn.config import TIER_BLURB, Tier
from app.earn.models import EarnProfile
from app.earn.opportunities import match_opportunities
from app.earn.readiness import (
    ReadinessReport,
    StreamReadiness,
    StreamState,
    build_readiness,
)
from app.earn.schemas import (
    CreativeSection,
    EligibilityVerdict,
    OpportunityOut,
    OpportunitySection,
    ProfileResponse,
    ReadinessResponse,
    StatsSnapshot,
    StreamCard,
)
from app.earn.signals import gather_signals
from app.earn.tiers import assess_tier

logger = logging.getLogger("app.earn.service")

_TIER_LABEL = {
    Tier.NANO: "Nano creator",
    Tier.MICRO: "Micro creator",
    Tier.MID: "Mid-tier creator",
    Tier.MACRO: "Macro creator",
}


# ─────────────────────────────────────────────────────────────────────────
#  Profile (the Q&A gate)
# ─────────────────────────────────────────────────────────────────────────


async def get_profile(session: AsyncSession, user_id: str) -> ProfileResponse:
    """Read the creator's Q&A profile. exists=False means show the gate."""
    row = await _load_profile(session, user_id)
    if row is None:
        return ProfileResponse(exists=False)
    return ProfileResponse(exists=True, answers=row.answers, updated_at=row.updated_at)


async def save_profile(
    session: AsyncSession, user_id: str, answers: dict[str, str]
) -> ProfileResponse:
    """Create or update the Q&A profile (upsert on the unique user_id)."""
    row = await _load_profile(session, user_id)
    if row is None:
        row = EarnProfile(user_id=user_id, answers=answers)
        session.add(row)
    else:
        row.answers = answers
    await session.commit()
    await session.refresh(row)
    return ProfileResponse(exists=True, answers=row.answers, updated_at=row.updated_at)


async def _load_profile(session: AsyncSession, user_id: str) -> EarnProfile | None:
    result = await session.execute(
        select(EarnProfile).where(EarnProfile.user_id == user_id)
    )
    return result.scalar_one_or_none()


# ─────────────────────────────────────────────────────────────────────────
#  Niche normalization (self-contained — does not import the research agent)
# ─────────────────────────────────────────────────────────────────────────

# Map common persona niche phrases to the simple keys we tag opportunities and
# run discovery with. Loose and forgiving; unknown niches fall through to None
# (→ universal matching only).
_NICHE_MAP: dict[str, str] = {
    "food": "food",
    "cooking": "food",
    "recipe": "food",
    "vlog": "food",
    "fitness": "fitness",
    "gym": "fitness",
    "health": "fitness",
    "workout": "fitness",
    "fashion": "fashion",
    "style": "fashion",
    "outfit": "fashion",
    "tech": "tech",
    "technology": "tech",
    "gadget": "tech",
    "coding": "tech",
    "software": "tech",
    "game": "gaming",
    "gaming": "gaming",
    "esports": "gaming",
    "beauty": "beauty",
    "makeup": "beauty",
    "skincare": "beauty",
    "travel": "travel",
    "tourism": "travel",
    "finance": "finance",
    "money": "finance",
    "invest": "finance",
    "crypto": "finance",
    "education": "education",
    "learning": "education",
    "study": "education",
    "tutorial": "education",
    "comedy": "comedy",
    "humor": "comedy",
    "humour": "comedy",
    "funny": "comedy",
    "meme": "comedy",
    "animation": "animation",
    "animator": "animation",
    "art": "animation",
    "design": "animation",
}


def normalize_niche(raw_niche: str | None) -> str | None:
    """Best-effort map a free-text persona niche to a tag key."""
    if not raw_niche:
        return None
    low = raw_niche.lower()
    for needle, key in _NICHE_MAP.items():
        if needle in low:
            return key
    return None


# ─────────────────────────────────────────────────────────────────────────
#  The full readiness pipeline
# ─────────────────────────────────────────────────────────────────────────


async def build_readiness_response(
    session: AsyncSession,
    user_id: str,
    answers: dict[str, str],
    raw_niche: str | None,
) -> ReadinessResponse:
    """signals → tier → readiness → opportunities + coach → four sections."""
    niche_key = normalize_niche(raw_niche)

    # 1. Gather signals (defensive; may be empty) → 2. tier → 3. readiness
    signals = await gather_signals(session, user_id)
    assessment = assess_tier(signals)
    report = build_readiness(assessment, answers)

    # 4. Opportunities (DB) + 5. coaching & ideas (LLM, with fallback)
    opportunities = await match_opportunities(session, report, niche_key)
    coach_summary = await coach.write_coaching(report, raw_niche)
    ideas = await coach.write_creative_ideas(report, raw_niche)

    # 6. Assemble the four sections
    return ReadinessResponse(
        stats=_build_stats(assessment),
        verdict=_build_verdict(report, coach_summary),
        opportunities=_build_opportunity_section(report, opportunities),
        creative=CreativeSection(
            intro="Creative, niche-specific ways to turn your content into income:",
            ideas=ideas,
        ),
        generated_at=datetime.now(UTC),
    )


# ── section builders ──────────────────────────────────────────────────────


def _build_stats(assessment) -> StatsSnapshot:
    s = assessment.signals
    return StatsSnapshot(
        total_followers=s.total_followers,
        monthly_views=s.monthly_views,
        total_posts=s.total_posts,
        connected_platforms=s.connected_platforms,
        tier=assessment.tier.value,
        tier_label=_TIER_LABEL.get(assessment.tier, "Creator"),
        tier_blurb=TIER_BLURB.get(assessment.tier, ""),
        confidence=assessment.confidence,
        engagement_note=assessment.flex_reason,
        has_data=s.has_data,
    )


def _card(sr: StreamReadiness) -> StreamCard:
    return StreamCard(
        stream_id=sr.stream_id,
        label=sr.label,
        category=sr.category,
        durability=sr.durability,
        effort=sr.effort,
        eligibility=sr.eligibility.value,
        interest=sr.interest,
        state=sr.state.value,
        tradeoff_label=sr.tradeoff_label,
        short_pitch=sr.short_pitch,
        time_to_first_revenue=sr.time_to_first_revenue,
        followers_gap=sr.followers_gap,
    )


def _build_verdict(report: ReadinessReport, coach_summary: str) -> EligibilityVerdict:
    green = [_card(s) for s in report.ranked_gaps if s.state == StreamState.GREEN_LIGHT]
    almost = [
        _card(s) for s in report.ranked_gaps if s.state == StreamState.ALMOST_THERE
    ]
    return EligibilityVerdict(
        coach_summary=coach_summary,
        green_lights=green,
        almost_there=almost,
        optimizing=[_card(s) for s in report.optimizing],
        foundation=[_card(s) for s in report.foundation],
    )


def _build_opportunity_section(report: ReadinessReport, opps) -> OpportunitySection:
    out = [
        OpportunityOut(
            id=str(o.id),
            opp_type=o.opp_type,
            title=o.title,
            brand_name=o.brand_name,
            description=o.description,
            commission_note=o.commission_note,
            url=o.url,
            source=o.source,
        )
        for o in opps
    ]

    has_green = any(s.state == StreamState.GREEN_LIGHT for s in report.ranked_gaps)

    if out:
        intro = "Opportunities matched to where you are and what you want to pursue:"
        empty = None
    elif has_green:
        intro = "Matched opportunities"
        empty = (
            "We're still gathering live opportunities for your niche. Meanwhile, your green-lit "
            "streams above are the place to start — the curated programs there work for any creator."
        )
    else:
        intro = "Matched opportunities"
        empty = (
            "Opportunities here unlock as you grow into brand-facing streams. For now, focus on the "
            "foundation streams in your plan above."
        )

    return OpportunitySection(intro=intro, opportunities=out, empty_message=empty)
