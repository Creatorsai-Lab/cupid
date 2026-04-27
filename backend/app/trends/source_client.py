"""
News Source Client — fetches headlines from external sources.

Strategy:
    1. PRIMARY:  Google News RSS (via `gnews` package)
       - Free, unlimited, real Google ranking
       - Occasionally blocked by Google → fall through
    2. FALLBACK: GNews API (api.gnews.io)
       - 100 req/day free
       - Used only when RSS fails

Why have a fallback?
    Single-source dependencies are fragile. If Google rate-limits our IP
    one afternoon, the entire Trends page goes blank. Having a paid-tier
    fallback (even with strict limits) keeps the product alive while we
    debug the primary source.

Note on async:
    `gnews` is a sync library. We use asyncio.to_thread to run it without
    blocking the event loop — same pattern as your duckduckgo-search wrapper.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# These are the niche buckets we ingest. Mapping our internal taxonomy
# to Google News topic codes. Anything not in here uses keyword search.
GOOGLE_NEWS_TOPICS: dict[str, str] = {
    "technology": "TECHNOLOGY",
    "business":   "BUSINESS",
    "health":     "HEALTH",
    "science":    "SCIENCE",
    "sports":     "SPORTS",
    "entertainment": "ENTERTAINMENT",
    "world":      "WORLD",
    "nation":     "NATION",
}

# Niches we use keyword-search for (no native Google topic)
KEYWORD_NICHES: dict[str, str] = {
    "ai":           "AI artificial intelligence",
    "crypto":       "cryptocurrency bitcoin",
    "fitness":      "fitness workout health",
    "marketing":    "marketing growth digital",
    "startups":     "startup founders venture capital",
    "design":       "design UX UI",
    "productivity": "productivity workflow tools",
}


@dataclass
class RawArticle:
    """Normalized shape across both RSS and API sources."""
    title: str
    description: str
    url: str
    image_url: str | None
    source: str
    domain: str
    published_at: datetime


# ──────────────────────────────────────────────────────────────────
#  PRIMARY: Google News RSS (via gnews library)
# ──────────────────────────────────────────────────────────────────

def _fetch_via_gnews_sync(category: str, max_results: int) -> list[dict[str, Any]]:
    """Sync RSS fetch — wrapped in to_thread by the caller."""
    from gnews import GNews

    client = GNews(language="en", country="IN", max_results=max_results, period="2d")

    if category in GOOGLE_NEWS_TOPICS:
        return client.get_news_by_topic(GOOGLE_NEWS_TOPICS[category])

    if category in KEYWORD_NICHES:
        return client.get_news(KEYWORD_NICHES[category])

    # Fallback: treat the category name itself as a search query
    return client.get_news(category)


async def fetch_via_rss(category: str, max_results: int = 20) -> list[RawArticle]:
    """Async wrapper around the sync gnews fetch."""
    try:
        raw = await asyncio.wait_for(
            asyncio.to_thread(_fetch_via_gnews_sync, category, max_results),
            timeout=20.0,
        )
    except Exception as exc:
        logger.warning("[trends.source] RSS fetch failed for %s: %s", category, exc)
        return []

    return [_parse_rss_item(item) for item in raw if item.get("url")]


def _parse_rss_item(item: dict[str, Any]) -> RawArticle:
    """Convert gnews dict to our normalized RawArticle."""
    url = item.get("url", "")
    domain = urlparse(url).netloc.replace("www.", "") if url else "unknown"

    # gnews returns 'published date' as a string, parse defensively
    published_at = _parse_date(item.get("published date", ""))

    title = _strip_publisher_suffix(item.get("title", ""))

    return RawArticle(
        title=title,
        description=item.get("description", ""),
        url=url,
        image_url=None,  # RSS doesn't expose images; fallback path may
        source=item.get("publisher", {}).get("title", domain) if isinstance(item.get("publisher"), dict) else domain,
        domain=domain,
        published_at=published_at,
    )


def _strip_publisher_suffix(title: str) -> str:
    """Google News appends ' - Publisher'. Strip it for cleaner display."""
    return re.sub(r"\s*-\s*[^-]+$", "", title).strip() or title


def _parse_date(raw: str) -> datetime:
    """Parse RFC 2822 date from RSS, fallback to now if malformed."""
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return datetime.now()


# ──────────────────────────────────────────────────────────────────
#  FALLBACK: GNews API (api.gnews.io)
# ──────────────────────────────────────────────────────────────────

GNEWS_API_BASE = "https://gnews.io/api/v4"


async def fetch_via_api(
    category: str,
    api_key: str,
    max_results: int = 10,
) -> list[RawArticle]:
    """
    Hit GNews API as fallback. Free tier = 100 calls/day total, so this
    runs only when RSS comes back empty.
    """
    if not api_key:
        return []

    # Map our category → GNews API topic param
    api_categories = {
        "technology": "technology", "business": "business",
        "health": "health", "science": "science",
        "sports": "sports", "entertainment": "entertainment",
        "world": "world", "nation": "nation",
    }

    if category in api_categories:
        url = f"{GNEWS_API_BASE}/top-headlines"
        params = {
            "category": api_categories[category],
            "lang": "en",
            "max": max_results,
            "apikey": api_key,
        }
    else:
        # Use search endpoint with keyword for niches not in API categories
        url = f"{GNEWS_API_BASE}/search"
        params = {
            "q": KEYWORD_NICHES.get(category, category),
            "lang": "en",
            "max": max_results,
            "apikey": api_key,
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("[trends.source] API fallback failed for %s: %s", category, exc)
        return []

    articles_raw = data.get("articles", [])
    return [_parse_api_article(a) for a in articles_raw]


def _parse_api_article(item: dict[str, Any]) -> RawArticle:
    """Convert GNews API article to RawArticle."""
    url = item.get("url", "")
    domain = urlparse(url).netloc.replace("www.", "") if url else "unknown"

    return RawArticle(
        title=item.get("title", ""),
        description=item.get("description", ""),
        url=url,
        image_url=item.get("image"),
        source=(item.get("source") or {}).get("name", domain),
        domain=domain,
        published_at=_parse_iso(item.get("publishedAt", "")),
    )


def _parse_iso(raw: str) -> datetime:
    """Parse ISO 8601 from GNews API."""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.now()


# ──────────────────────────────────────────────────────────────────
#  Public API: try RSS, fall back to API if empty
# ──────────────────────────────────────────────────────────────────

async def fetch_category(
    category: str,
    api_key: str | None = None,
    max_results: int = 20,
) -> list[RawArticle]:
    """
    Fetch articles for a category. RSS first, API as fallback.

    Caller is responsible for deduplication and persistence.
    """
    articles = await fetch_via_rss(category, max_results)
    if articles:
        logger.info("[trends.source] %s: %d articles via RSS", category, len(articles))
        return articles

    if api_key:
        logger.warning("[trends.source] %s: RSS empty, trying API fallback", category)
        articles = await fetch_via_api(category, api_key, max_results)
        logger.info("[trends.source] %s: %d articles via API", category, len(articles))
        return articles

    logger.warning("[trends.source] %s: RSS empty, no API key configured", category)
    return []