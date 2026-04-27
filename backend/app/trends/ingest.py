"""
Trends Ingestion — runs in the background, populates the DB.

Pipeline:
    for each tracked category:
        fetch via source_client (RSS → API fallback)
        compute velocity score (recency × source authority)
        upsert into trending_articles (idempotent by url_hash)

This runs on a schedule (every 30 min by default). It is idempotent —
you can call it as often as you want, the same article only ever gets
written once thanks to the url_hash primary key.

Latency budget:
    For 10 categories × ~20 articles = ~200 articles per run.
    RSS fetch: ~1-3s per category, parallel = ~5s total
    DB writes: ~50-100ms total via single transaction
    Total run time: <10 seconds

That's fine for a 30-min cron. We're not optimizing for ingestion speed.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session as async_session_factory
from app.trends.source_client import RawArticle, fetch_category
from app.models.trending_article import TrendingArticle
from app.config import settings

logger = logging.getLogger(__name__)

# Categories we ingest on every run. Add/remove freely.
TRACKED_CATEGORIES: tuple[str, ...] = (
    "technology", "business", "health", "science", "sports",
    "entertainment", "ai", "crypto", "marketing", "startups",
    "fitness", "design", "productivity", "world",
)


# ──────────────────────────────────────────────────────────────────
#  Velocity scoring (computed once, persisted)
# ──────────────────────────────────────────────────────────────────

# Loose authority weights — major outlets get a small boost.
# This is a heuristic, not science. Refine based on your audience.
_AUTHORITY: dict[str, float] = {
    "reuters.com":      0.95,
    "apnews.com":       0.95,
    "bbc.com":          0.90,
    "bbc.co.uk":        0.90,
    "nytimes.com":      0.90,
    "wsj.com":          0.90,
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
    """
    velocity = 0.6·authority + 0.4·freshness

    Computed once at ingestion. Persisted on the row. Read-only at serving.
    """
    authority = _AUTHORITY.get(article.domain, 0.5)

    # Freshness: 1.0 if just published, decaying linearly over 48h
    age_hours = (datetime.now(timezone.utc) - _ensure_aware(article.published_at)).total_seconds() / 3600
    freshness = max(0.0, 1.0 - age_hours / 48.0)

    return round(0.6 * authority + 0.4 * freshness, 4)


def _ensure_aware(dt: datetime) -> datetime:
    """Some RSS feeds give naive datetimes. Treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ──────────────────────────────────────────────────────────────────
#  URL hashing for stable primary key
# ──────────────────────────────────────────────────────────────────

def _url_hash(url: str) -> str:
    """Stable 32-char hash of the URL — collision-free in practice."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]


# ──────────────────────────────────────────────────────────────────
#  Bulk upsert — Postgres-specific but very fast
# ──────────────────────────────────────────────────────────────────

async def _persist_articles(
    session: AsyncSession,
    category: str,
    articles: Iterable[RawArticle],
) -> int:
    """
    Insert articles, skip duplicates. Returns count of new rows.

    Why ON CONFLICT DO NOTHING?
        Without it, a duplicate URL would raise IntegrityError and abort
        the whole transaction. The "DO NOTHING" makes inserts idempotent —
        we can re-run ingestion safely.
    """
    rows = []
    for art in articles:
        if not art.url or not art.title:
            continue
        rows.append({
            "url_hash":     _url_hash(art.url),
            "title":        art.title[:512],          # respect column length
            "description":  art.description or None,
            "url":          art.url,
            "image_url":    art.image_url,
            "source":       art.source[:128],
            "domain":       art.domain[:128],
            "category":     category,
            "published_at": _ensure_aware(art.published_at),
            "velocity_score": _compute_velocity(art),
        })

    if not rows:
        return 0

    # Postgres-specific: ON CONFLICT (primary_key) DO NOTHING
    stmt = insert(TrendingArticle).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["url_hash"])

    result = await session.execute(stmt)
    return result.rowcount or 0


# ──────────────────────────────────────────────────────────────────
#  Main ingestion entry point — Celery task wraps this
# ──────────────────────────────────────────────────────────────────

async def ingest_all_categories() -> dict[str, int]:
    """
    Fetch + persist every tracked category. Categories run in parallel
    (each one is mostly I/O on RSS — perfect for asyncio.gather).

    Returns: {category: new_articles_count}
    """
    api_key = getattr(settings, "gnews_api_key", None) or None

    # Parallel fetch across categories
    fetch_tasks = [
        fetch_category(cat, api_key=api_key, max_results=20)
        for cat in TRACKED_CATEGORIES
    ]
    results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    # Single DB session for all writes — one transaction, atomic
    summary: dict[str, int] = {}
    async with async_session_factory() as session:
        for category, fetched in zip(TRACKED_CATEGORIES, results, strict=True):
            if isinstance(fetched, Exception):
                logger.error("[trends.ingest] %s failed: %s", category, fetched)
                summary[category] = 0
                continue

            inserted = await _persist_articles(session, category, fetched)
            summary[category] = inserted
            logger.info(
                "[trends.ingest] %s: %d fetched, %d new",
                category, len(fetched), inserted,
            )

        await session.commit()

    total_new = sum(summary.values())
    logger.info("[trends.ingest] DONE — %d new articles total", total_new)
    return summary