"""
app/earn/discovery.py
═══════════════════════════════════════════════════════════════════════════

The opportunity discovery job: periodically web-searches for PUBLIC, evergreen
monetization opportunities (affiliate programs, brand ambassador pages) per
niche and upserts them into the archive.

WHY SEARCH, NOT SCRAPE GATED MARKETPLACES
─────────────────────────────────────────
The fresh "brands looking for influencers right now" listings live behind
login walls whose terms forbid scraping. So we DON'T point a crawler at them.
Instead we search for what's genuinely public and stable:
  • "<niche> affiliate program" — programs advertise themselves publicly.
  • "<niche> brand ambassador program apply" — evergreen recruitment pages.
This is durable (these pages don't vanish weekly), legitimate (public, meant
to be found), and degrades gracefully (curated seeds cover any gap).

SELF-CONTAINED + HANG-PROOF
───────────────────────────
This does NOT reuse the research agent's search.py. It's its own small
searcher — but it bakes in the hard lesson from fixing that file:

  • a NATIVE timeout on the DDGS client (so the blocking call itself can't
    hang forever — asyncio.wait_for alone can't kill a stuck thread), and
  • a DEDICATED bounded executor (so a leaked search thread can't starve the
    rest of the app's thread pool).

If the search library is unavailable or every query fails, discovery simply
finds nothing this cycle and the curated seeds carry the feature. It never
raises into the scheduler.
"""
from __future__ import annotations

import asyncio
import functools
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.earn.models import (
    OPP_AFFILIATE,
    OPP_AMBASSADOR,
    SOURCE_DISCOVERED,
    EarnOpportunity,
)

logger = logging.getLogger("app.earn.discovery")

# Native socket timeout for the search client, in seconds. The blocking call
# physically cannot exceed this — the fix that actually stops hangs.
_DDG_TIMEOUT = 8.0
# Outer async net, comfortably above the native timeout.
_OUTER_TIMEOUT = _DDG_TIMEOUT + 3.0
_RESULTS_PER_QUERY = 6


@dataclass(frozen=True)
class _Candidate:
    opp_type: str
    title: str
    url: str
    description: str
    niche_key: str


# The query templates per opportunity type. {niche} is filled per niche.
_QUERY_TEMPLATES: tuple[tuple[str, str], ...] = (
    (OPP_AFFILIATE, "{niche} affiliate program"),
    (OPP_AMBASSADOR, "{niche} brand ambassador program apply"),
)


class OpportunityDiscovery:
    """One instance owns the dedicated search executor for its lifetime."""

    def __init__(self) -> None:
        # Dedicated, bounded pool. A hung search thread can only ever exhaust
        # THIS (size 3), never the global executor the app relies on.
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="earn-discovery")

    def close(self) -> None:
        # wait=False so shutdown can't itself block on a stuck thread.
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ── one search ────────────────────────────────────────────────────────
    async def _search(self, opp_type: str, niche: str) -> list[_Candidate]:
        query = next(t for k, t in _QUERY_TEMPLATES if k == opp_type).format(niche=niche)

        def _sync() -> list[dict]:
            # NATIVE timeout on the client — see module docstring for why this
            # is the load-bearing line, not the asyncio.wait_for below.
            from ddgs import DDGS
            with DDGS(timeout=_DDG_TIMEOUT) as ddgs:
                return list(ddgs.text(query, max_results=_RESULTS_PER_QUERY))

        try:
            loop = asyncio.get_running_loop()
            raw = await asyncio.wait_for(
                loop.run_in_executor(self._executor, functools.partial(_sync)),
                timeout=_OUTER_TIMEOUT,
            )
        except Exception as exc:  # noqa: BLE001 — timeouts, rate limits, import errors
            logger.info("[earn.discovery] search '%s' failed (%s)", query, str(exc)[:120])
            return []

        out: list[_Candidate] = []
        for r in raw:
            url = (r.get("href") or r.get("url") or "").strip()
            title = (r.get("title") or "").strip()
            body = (r.get("body") or "").strip()
            if not url or not title:
                continue
            out.append(
                _Candidate(
                    opp_type=opp_type,
                    title=title[:300],
                    url=url[:1000],
                    description=body[:500] or None,
                    niche_key=niche.lower(),
                )
            )
        return out

    # ── full cycle for a set of niches ─────────────────────────────────────
    async def discover(self, session: AsyncSession, niches: list[str]) -> int:
        """
        Run all (type × niche) searches, upsert new finds. Returns count added.
        Best-effort: per-search failures are swallowed; the cycle continues.
        """
        candidates: list[_Candidate] = []
        for niche in niches:
            for opp_type, _ in _QUERY_TEMPLATES:
                candidates.extend(await self._search(opp_type, niche))

        if not candidates:
            logger.info("[earn.discovery] no candidates this cycle")
            return 0

        return await self._upsert(session, candidates)

    async def _upsert(self, session: AsyncSession, candidates: list[_Candidate]) -> int:
        """Insert candidates whose URL isn't already in the archive."""
        added = 0
        try:
            for c in candidates:
                exists = await session.execute(
                    select(EarnOpportunity.id).where(EarnOpportunity.url == c.url)
                )
                if exists.first() is not None:
                    continue
                session.add(
                    EarnOpportunity(
                        opp_type=c.opp_type,
                        title=c.title,
                        brand_name=None,
                        description=c.description,
                        niche_tags=[c.niche_key],
                        min_tier="nano" if c.opp_type == OPP_AFFILIATE else "micro",
                        commission_note=None,
                        url=c.url,
                        source=SOURCE_DISCOVERED,
                        is_active=True,
                    )
                )
                added += 1
            if added:
                await session.commit()
                logger.info("[earn.discovery] added %d discovered opportunities", added)
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            logger.warning("[earn.discovery] upsert failed (%s)", str(exc)[:160])
        return added