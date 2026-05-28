"""
app/earn/opportunities.py
═══════════════════════════════════════════════════════════════════════════

Section 3's engine: given a creator's readiness report and niche, return the
archive opportunities worth showing them — filtered by what they're eligible
for, what they want, and their niche, ranked curated-first.

MATCHING LOGIC
──────────────
An opportunity is shown when ALL hold:
  • it's active,
  • the creator's tier meets the opportunity's min_tier,
  • its type maps to a stream the creator is GREEN_LIGHT or ALMOST_THERE on
    (i.e. they want it and can/almost can do it) — we don't surface brand-deal
    leads to someone who said "not interested" in brand deals,
  • its niche tags overlap the creator's niche, or it's tagged "all".

Curated entries rank above discovered ones (higher trust), then newest first.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.earn.config import TIER_ORDER, Tier
from app.earn.models import (
    OPP_AFFILIATE,
    OPP_AMBASSADOR,
    OPP_BRAND_DEAL,
    SOURCE_CURATED,
    EarnOpportunity,
)
from app.earn.readiness import ReadinessReport, StreamState

logger = logging.getLogger("app.earn.opportunities")


# Which streams "unlock" which opportunity types. A creator pursuing these
# streams should see these opportunity types.
_STREAM_TO_OPP_TYPES: dict[str, set[str]] = {
    "affiliate": {OPP_AFFILIATE},
    "brand_deals": {OPP_BRAND_DEAL},
    "brand_ambassador": {OPP_AMBASSADOR},
}


def _tier_index(tier_value: str) -> int:
    """Position of a tier string in the low→high order; -1 if unknown."""
    try:
        return TIER_ORDER.index(Tier(tier_value))
    except (ValueError, KeyError):
        return -1


def _wanted_opp_types(report: ReadinessReport) -> set[str]:
    """The opportunity types the creator is actively pursuing (green/almost)."""
    pursuing = {
        s.stream_id
        for s in report.ranked_gaps
        if s.state in (StreamState.GREEN_LIGHT, StreamState.ALMOST_THERE)
    }
    types: set[str] = set()
    for stream_id in pursuing:
        types |= _STREAM_TO_OPP_TYPES.get(stream_id, set())
    return types


def _niche_matches(opp_tags: list, niche_key: str | None) -> bool:
    """True if the opportunity is universal or shares the creator's niche."""
    if not opp_tags:
        return True
    tags = {str(t).lower() for t in opp_tags}
    if "all" in tags:
        return True
    if niche_key and niche_key.lower() in tags:
        return True
    return False


async def match_opportunities(
    session: AsyncSession,
    report: ReadinessReport,
    niche_key: str | None,
    limit: int = 12,
) -> list[EarnOpportunity]:
    """
    Return the opportunities worth showing this creator, best-first.

    Never raises — on any DB problem returns [] so Section 3 simply shows its
    honest empty-state instead of breaking the page.
    """
    wanted_types = _wanted_opp_types(report)
    if not wanted_types:
        # The creator isn't pursuing any opportunity-backed stream (e.g. they
        # only want a paid community). Nothing to match — Section 3 will show
        # its "focus on your green lights first" message.
        return []

    creator_tier_idx = _tier_index(report.tier.value)

    try:
        # Pull active candidates of the wanted types; filter tier + niche in
        # Python (the candidate set is small and this keeps the query simple
        # and portable). The composite index still accelerates the WHERE.
        stmt = (
            select(EarnOpportunity)
            .where(
                EarnOpportunity.is_active.is_(True),
                EarnOpportunity.opp_type.in_(wanted_types),
            )
            .limit(200)  # generous candidate cap; we rank/trim below
        )
        result = await session.execute(stmt)
        candidates = list(result.scalars().all())
    except Exception as exc:  # noqa: BLE001
        logger.warning("[earn.opportunities] query failed (%s) — empty section", str(exc)[:160])
        return []

    # Filter by tier reachability and niche.
    matched = [
        opp
        for opp in candidates
        if _tier_index(opp.min_tier) <= creator_tier_idx
        and _niche_matches(opp.niche_tags, niche_key)
    ]

    # Rank: curated before discovered, then newest discovered first.
    matched.sort(
        key=lambda o: (
            0 if o.source == SOURCE_CURATED else 1,
            -(o.discovered_at.timestamp() if o.discovered_at else 0),
        )
    )
    return matched[:limit]