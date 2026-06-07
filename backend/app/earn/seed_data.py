"""
app/earn/seed_data.py
═══════════════════════════════════════════════════════════════════════════

Hand-curated, evergreen opportunities that guarantee Section 3 has real,
trustworthy content from day one — before the discovery job has found
anything. These are well-known, publicly-joinable programs with stable URLs.

WHY SEED AT ALL
───────────────
An opportunity board that's empty on launch teaches users the feature is
dead. Seeding with a handful of genuinely useful, universally-applicable
programs means every creator sees value immediately, and the discovery job
enriches from there. Curated entries also rank above discovered ones, so the
quality floor stays high.

Keep this list SMALL and HIGH-QUALITY. It's a starting floor, not a directory.
The seeding function is idempotent — safe to run on every startup; it won't
create duplicates.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.earn.models import (
    OPP_AFFILIATE,
    OPP_AMBASSADOR,
    SOURCE_CURATED,
    EarnOpportunity,
)

logger = logging.getLogger("app.earn.seed")


# Each tuple: (opp_type, title, brand, description, niche_tags, min_tier,
#              commission_note, url)
# niche_tags ["all"] = universally applicable. min_tier "nano" = anyone.
_SEED: tuple[dict, ...] = (
    {
        "opp_type": OPP_AFFILIATE,
        "title": "Amazon Associates",
        "brand_name": "Amazon",
        "description": "The most accessible affiliate program — link almost any product and earn "
        "commission. Ideal first affiliate program for any niche.",
        "niche_tags": ["all"],
        "min_tier": "nano",
        "commission_note": "Varies by category",
        "url": "https://affiliate-program.amazon.com/",
    },
    {
        "opp_type": OPP_AFFILIATE,
        "title": "Impact Marketplace",
        "brand_name": "Impact.com",
        "description": "A large marketplace of brand affiliate programs across many niches — "
        "browse and apply to ones that fit your content.",
        "niche_tags": ["all"],
        "min_tier": "nano",
        "commission_note": "Varies by brand",
        "url": "https://impact.com/creators/",
    },
    {
        "opp_type": OPP_AFFILIATE,
        "title": "ShareASale Network",
        "brand_name": "ShareASale",
        "description": "Long-running affiliate network with thousands of merchants, strong for "
        "lifestyle, home, fashion, and DIY niches.",
        "niche_tags": ["all"],
        "min_tier": "nano",
        "commission_note": "Varies by merchant",
        "url": "https://www.shareasale.com/",
    },
    {
        "opp_type": OPP_AFFILIATE,
        "title": "Awin Affiliate Network",
        "brand_name": "Awin",
        "description": "Global affiliate network with a large brand catalog; accessible sign-up "
        "for newer creators (small refundable deposit).",
        "niche_tags": ["all"],
        "min_tier": "nano",
        "commission_note": "Varies by brand",
        "url": "https://www.awin.com/",
    },
    {
        "opp_type": OPP_AMBASSADOR,
        "title": "Collabstr Creator Marketplace",
        "brand_name": "Collabstr",
        "description": "List yourself and get discovered by brands seeking creators for paid "
        "collaborations — strong for micro and mid creators.",
        "niche_tags": ["all"],
        "min_tier": "micro",
        "commission_note": None,
        "url": "https://collabstr.com/",
    },
    {
        "opp_type": OPP_AMBASSADOR,
        "title": "Afluencer Brand Collabs",
        "brand_name": "Afluencer",
        "description": "Free-to-join platform with AI brand matching, well-suited to nano and "
        "micro creators landing their first collaborations.",
        "niche_tags": ["all"],
        "min_tier": "nano",
        "commission_note": None,
        "url": "https://afluencer.com/",
    },
)


async def seed_opportunities(session: AsyncSession) -> int:
    """
    Insert any curated opportunities not already present. Idempotent: matches
    on (title, url) so re-running never duplicates. Returns count inserted.
    """
    inserted = 0
    try:
        for entry in _SEED:
            exists = await session.execute(
                select(EarnOpportunity.id).where(
                    EarnOpportunity.title == entry["title"],
                    EarnOpportunity.url == entry["url"],
                )
            )
            if exists.first() is not None:
                continue
            session.add(EarnOpportunity(source=SOURCE_CURATED, is_active=True, **entry))
            inserted += 1
        if inserted:
            await session.commit()
            logger.info("[earn.seed] inserted %d curated opportunities", inserted)
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        logger.warning("[earn.seed] seeding failed (%s)", str(exc)[:160])
    return inserted
