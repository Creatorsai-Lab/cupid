"""
Trends Service — request-time logic for the /trends/news endpoint.

This module sits between the router and the database. It owns:
    1. The Redis cache (avoid recomputing for the same user repeatedly)
    2. The DB query (pull recent articles in user's niches)
    3. The per-user ranking (delegate to ranker.py)
    4. Response assembly (turn ORM rows into Pydantic schemas)

Cache strategy:
    - Key: f"trends:user:{user_id}"
    - TTL: 10 minutes
    - Invalidation: time-based only. We don't bust on persona update —
      next refresh will pick up the new persona naturally.

Why 10 min and not, say, 5 min?
    Trade-off between freshness and API speed. Articles only update every
    30 min in the DB, so a 10-min user cache rarely shows stale data.
    Bumping to 60s would help freshness but multiply DB load 10x.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.trends.ranker import rank_articles
from app.schemas.trends import TrendingArticle, TrendsResponse
# Import the Database Model (for SQLAlchemy) and alias it
from app.models.trending_article import TrendingArticle as DBArticles

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 600          # 10 min — see module docstring
RECENT_WINDOW_HOURS = 36         # only consider articles from last 36h
POOL_SIZE = 60                   # how many articles to rank from


# User niches are free-text from the personalization form. We map them
# down to our coarse-grained ingestion categories. This is fuzzy on
# purpose — better to over-fetch than to miss articles.

_NICHE_TO_CATEGORIES: dict[str, list[str]] = {
    "ai/ml":       ["ai", "technology", "science"],
    "ai":          ["ai", "technology"],
    "software":    ["technology", "ai"],
    "tech":        ["technology", "ai"],
    "marketing":   ["marketing", "business"],
    "startups":    ["startups", "business", "technology"],
    "finance":     ["business", "crypto"],
    "crypto":      ["crypto", "business"],
    "health":      ["health", "fitness"],
    "fitness":     ["fitness", "health"],
    "design":      ["design", "technology"],
    "creator":     ["entertainment", "marketing"],
    "productivity": ["productivity", "technology"],
    "science":     ["science", "health"],
    "sports":      ["sports"],
    "entertainment": ["entertainment"],
}


def _resolve_categories(niche: str | None) -> list[str]:
    """Map free-text niche → list of DB categories to query."""
    if not niche:
        return ["technology", "business", "world"]    # safe defaults

    n = niche.lower().strip()

    # Exact match
    if n in _NICHE_TO_CATEGORIES:
        return _NICHE_TO_CATEGORIES[n]

    # Substring match — "AI / Machine Learning" → "ai/ml"
    for key, cats in _NICHE_TO_CATEGORIES.items():
        if key in n or any(part in n for part in key.split("/")):
            return cats

    # No match — pull from broad buckets
    return ["technology", "business", "world"]


# ──────────────────────────────────────────────────────────────────
#  Redis cache helpers
# ──────────────────────────────────────────────────────────────────

def _cache_key(user_id: str) -> str:
    return f"trends:user:{user_id}"


async def _read_cache(redis: Redis, user_id: str) -> TrendsResponse | None:
    """Try cache. Return None on miss or any error (cache failures must
    never break the user-facing path)."""
    try:
        raw = await redis.get(_cache_key(user_id))
        if not raw:
            return None
        data = json.loads(raw)
        # Reconstruct from JSON — Pydantic handles datetime parsing
        return TrendsResponse.model_validate(data)
    except Exception as exc:
        logger.warning("[trends.cache] read miss/error: %s", exc)
        return None


async def _write_cache(redis: Redis, user_id: str, response: TrendsResponse) -> None:
    """Best-effort cache write. Never fails the request."""
    try:
        await redis.set(
            _cache_key(user_id),
            response.model_dump_json(),
            ex=CACHE_TTL_SECONDS,
        )
    except Exception as exc:
        logger.warning("[trends.cache] write failed: %s", exc)


# ──────────────────────────────────────────────────────────────────
#  Main public API
# ──────────────────────────────────────────────────────────────────

async def get_trends_for_user(
    user_id: str,
    persona: dict,
    session: AsyncSession,
    redis: Redis,
    bypass_cache: bool = False,
    top_k: int = 9,
) -> TrendsResponse:
    """
    Return the user's personalized trending news feed.

    Steps:
        1. Try Redis cache (return immediately on hit)
        2. Resolve user's niche → DB categories
        3. Pull pool of recent articles in those categories
        4. Run personalized ranker → top K
        5. Build response, cache it, return

    Latency on cache miss: ~200-400ms typical.
    Latency on cache hit:  ~5-10ms.
    """

    # 1) Cache fast path
    if not bypass_cache:
        cached = await _read_cache(redis, user_id)
        if cached is not None:
            cached.cached = True
            return cached

    # 2) Resolve niche → categories to query
    niche = persona.get("content_niche") or ""
    categories = _resolve_categories(niche)

    # 3) Pull recent articles from those categories
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RECENT_WINDOW_HOURS)
    stmt = (
        select(DBArticles)
        .where(DBArticles.category.in_(categories))
        .where(DBArticles.published_at >= cutoff)
        .order_by(DBArticles.published_at.desc())
        .limit(POOL_SIZE)
    )
    result = await session.execute(stmt)
    pool = list(result.scalars().all())

    if not pool:
        logger.info("[trends.serve] no articles for niche=%r — empty response", niche)
        return TrendsResponse(
            articles=[],
            niche=niche or "general",
            total_pool=0,
            cached=False,
            generated_at=datetime.now(timezone.utc),
        )

    # 4) Personalize the ranking for this specific user
    top = rank_articles(pool, persona, top_k=top_k)

    # 5) Convert ORM rows → Pydantic response
    articles = [
        TrendingArticle(
            id=row.url_hash,
            title=row.title,
            description=row.description,
            url=row.url,
            image_url=row.image_url,
            source=row.source,
            domain=row.domain,
            published_at=row.published_at,
            category=row.category,
            relevance_score=getattr(row, "relevance_score", 0.0),
            velocity_score=row.velocity_score,
        )
        for row in top
    ]

    response = TrendsResponse(
        articles=articles,
        niche=niche or "general",
        total_pool=len(pool),
        cached=False,
        generated_at=datetime.now(timezone.utc),
    )

    # 6) Best-effort cache write (don't await on the critical path)
    await _write_cache(redis, user_id, response)

    return response