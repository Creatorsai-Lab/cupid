"""
Trends Ingestion — runs in the background, populates the DB.

Rate-limit hygiene:
    - Sequential category fetching (no asyncio.gather)
    - 3-second base stagger between calls + jitter
    - Per-call retry-with-backoff is in source_client
    - Reduced category list — quality over quantity per run

Run schedule (when Celery is hooked up):
    Every 30 minutes. ~7 categories × 3s stagger = ~25s per run.
    Fetches ~7-15 RSS requests per run = well under Google's tolerance.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session as async_session_factory
from app.config import settings
from app.models.trending_article import TrendingArticle
from app.trends.source_client import RawArticle, fetch_category

logger = logging.getLogger(__name__)

# Core categories — fetched on every run
CORE_CATEGORIES: tuple[str, ...] = (
    "technology", "business", "world", "ai",
    "health", "science", "entertainment",
)

# Niche categories — rotated, only some per run to reduce request load
ROTATING_CATEGORIES: tuple[str, ...] = (
    "crypto", "marketing", "startups", "fitness",
    "design", "productivity", "sports",
)

# Track which rotating categories were last fetched (in-memory)
_last_rotated_index = 0


def _select_categories_for_run() -> list[str]:
    """Pick which categories this run will fetch."""
    global _last_rotated_index

    # Always do the core 7
    selected = list(CORE_CATEGORIES)

    # Add 3 rotating categories per run (so the full rotating list cycles
    # through every ~3 runs)
    rotation_size = 3
    rotating = list(ROTATING_CATEGORIES)
    start = _last_rotated_index % len(rotating)
    end = start + rotation_size
    if end <= len(rotating):
        chosen = rotating[start:end]
    else:
        chosen = rotating[start:] + rotating[: end - len(rotating)]
    _last_rotated_index = end % len(rotating)

    selected.extend(chosen)
    return selected


# ──────────────────────────────────────────────────────────────────
#  Velocity scoring
# ──────────────────────────────────────────────────────────────────

_AUTHORITY: dict[str, float] = {
    "reuters.com":      0.95,
    "timesofindia.indiatimes.com":       0.95,
    "hindustantimes.com": 0.95,
    "wsj.com":          0.95,
    "aninews.in":       0.95,
    "republicworld.com": 0.90,
    "ft.com":           0.90,
    "bloomberg.com":    0.85,
    "theverge.com":     0.80,
    "techcrunch.com":   0.80,
    "arstechnica.com":  0.80,
    "wired.com":        0.78,
    "guardian.com":     0.78,
    "axios.com":        0.75,
    "cnbc.com":         0.75,
    "forbes.com":       0.70,
}


def _compute_velocity(article: RawArticle) -> float:
    authority = _AUTHORITY.get(article.domain, 0.5)
    age_hours = (datetime.now(timezone.utc) - _ensure_aware(article.published_at)).total_seconds() / 3600
    freshness = max(0.0, 1.0 - age_hours / 48.0)
    return round(0.6 * authority + 0.4 * freshness, 4)


def _ensure_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]


# ──────────────────────────────────────────────────────────────────
#  Persist with upsert
# ──────────────────────────────────────────────────────────────────

async def _persist_articles(
    session: AsyncSession,
    category: str,
    articles: Iterable[RawArticle],
) -> int:
    rows = []
    for art in articles:
        if not art.url or not art.title:
            continue
        rows.append({
            "url_hash":       _url_hash(art.url),
            "title":          art.title[:512],
            "description":    art.description or None,
            "url":            art.url,
            "image_url":      art.image_url,
            "source":         art.source[:128],
            "domain":         art.domain[:128],
            "category":       category,
            "published_at":   _ensure_aware(art.published_at),
            "velocity_score": _compute_velocity(art),
        })

    if not rows:
        return 0

    stmt = insert(TrendingArticle).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["url_hash"])
    result = await session.execute(stmt)
    return result.rowcount or 0


# ──────────────────────────────────────────────────────────────────
#  Main ingestion entry point
# ──────────────────────────────────────────────────────────────────

async def ingest_all_categories() -> dict[str, int]:
    """
    Sequential ingestion with stagger — respects rate limits.
    Returns: {category: new_articles_count}
    """
    api_key = getattr(settings, "gnews_api_key", None) or None
    summary: dict[str, int] = {}

    categories_this_run = _select_categories_for_run()
    logger.info("[trends.ingest] this run will fetch: %s", categories_this_run)

    async with async_session_factory() as session:
        for i, category in enumerate(categories_this_run):
            # Stagger requests: 3s base + 0-1s jitter
            if i > 0:
                stagger = 3.0 + random.uniform(0, 1.0)
                await asyncio.sleep(stagger)

            try:
                fetched = await fetch_category(
                    category, api_key=api_key, max_results=20,
                )
            except Exception as exc:
                logger.error("[trends.ingest] %s fetch raised: %s", category, exc)
                summary[category] = 0
                continue

            if not fetched:
                summary[category] = 0
                continue

            try:
                inserted = await _persist_articles(session, category, fetched)
            except Exception as exc:
                logger.error("[trends.ingest] %s persist failed: %s", category, exc)
                await session.rollback()
                summary[category] = 0
                continue

            summary[category] = inserted
            logger.info(
                "[trends.ingest] %s: %d fetched, %d new",
                category, len(fetched), inserted,
            )

        await session.commit()

    total_new = sum(summary.values())
    logger.info("[trends.ingest] DONE — %d new articles total", total_new)
    return summary