"""
app/earn/scheduler.py
═══════════════════════════════════════════════════════════════════════════

Background maintenance for the opportunity archive, mirroring the pattern of
your trends and insights schedulers:

  • On startup: seed curated opportunities (idempotent).
  • Periodically: run the discovery job to enrich the archive from public
    search, then sleep.

Self-contained and fail-soft: any error in a cycle is logged and the loop
continues. The web feature never depends on this loop having succeeded —
curated seeds guarantee a useful Section 3 regardless.
"""

from __future__ import annotations

import asyncio
import logging

from app.earn.discovery import OpportunityDiscovery
from app.earn.seed_data import seed_opportunities

logger = logging.getLogger("app.earn.scheduler")

# How often to run discovery. These pages are evergreen, so daily is plenty.
_DISCOVERY_INTERVAL_SECONDS = 24 * 60 * 60
# Niches to discover for in each cycle. Start with a small, broad set; expand
# as you learn which niches your users actually have. (Could later be derived
# from the distinct niches present across user personas.)
_DISCOVERY_NICHES = [
    "food",
    "fitness",
    "fashion",
    "tech",
    "gaming",
    "beauty",
    "travel",
    "finance",
    "education",
    "comedy",
]


async def run_earn_scheduler(session_factory) -> None:
    """
    Long-running background task. `session_factory` is your async_session
    factory; we open a fresh session per unit of work (never hold one open
    across a sleep).
    """
    logger.info("[earn.scheduler] starting")

    # ── Startup: seed curated opportunities ──────────────────────────────
    try:
        async with session_factory() as session:
            await seed_opportunities(session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[earn.scheduler] initial seed failed (%s)", str(exc)[:160])

    # ── Periodic discovery loop ──────────────────────────────────────────
    discovery = OpportunityDiscovery()
    try:
        while True:
            try:
                async with session_factory() as session:
                    added = await discovery.discover(session, _DISCOVERY_NICHES)
                logger.info("[earn.scheduler] discovery cycle complete (+%d)", added)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[earn.scheduler] discovery cycle failed (%s)", str(exc)[:160]
                )

            await asyncio.sleep(_DISCOVERY_INTERVAL_SECONDS)
    finally:
        discovery.close()
