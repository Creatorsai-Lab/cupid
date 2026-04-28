"""
News Source Client — fetches headlines with proper rate-limit hygiene.

Strategy revisions (from previous version):
    - Sequential, not parallel — Google News flags burst requests
    - 2-3 second stagger between calls instead of 0.5s
    - User-Agent header that looks more like a real RSS reader
    - Retry-on-failure with exponential backoff
    - Fewer categories per run (split into "core" + "rotating")

Rate limit reality:
    - Google News RSS: silent throttling, ~10-20 requests/hour safe
    - GNews API free tier: 100 requests/day total
    - We fetch 7 core categories per run; 4 runs/day = 28 RSS requests = safe
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Browser-like UA helps avoid being identified as a bot
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Categories with native Google News topic codes
GOOGLE_NEWS_TOPICS: dict[str, str] = {
    "technology":    "TECHNOLOGY",
    "business":      "BUSINESS",
    "health":        "HEALTH",
    "science":       "SCIENCE",
    "sports":        "SPORTS",
    "entertainment": "ENTERTAINMENT",
    "world":         "WORLD",
    "nation":        "NATION",
}

# Niches handled via keyword search instead
KEYWORD_NICHES: dict[str, str] = {
    "ai":           "AI artificial intelligence",
    "crypto":       "cryptocurrency bitcoin",
    "fitness":      "fitness workout",
    "marketing":    "marketing growth digital",
    "startups":     "startup founders venture capital",
    "design":       "design UX UI",
    "productivity": "productivity workflow tools",
}


@dataclass
class RawArticle:
    title: str
    description: str
    url: str
    image_url: str | None
    source: str
    domain: str
    published_at: datetime


# ──────────────────────────────────────────────────────────────────
#  PRIMARY: Google News RSS via gnews library
# ──────────────────────────────────────────────────────────────────

def _fetch_via_gnews_sync(category: str, max_results: int) -> list[dict[str, Any]]:
    """Sync RSS fetch — wrapped in to_thread by the caller."""
    from gnews import GNews

    client = GNews(
        language="en",
        country="US",
        max_results=max_results,
        period="2d",
    )

    if category in GOOGLE_NEWS_TOPICS:
        return client.get_news_by_topic(GOOGLE_NEWS_TOPICS[category])
    if category in KEYWORD_NICHES:
        return client.get_news(KEYWORD_NICHES[category])
    return client.get_news(category)


async def fetch_via_rss(
    category: str,
    max_results: int = 20,
    retry_attempts: int = 2,
) -> list[RawArticle]:
    """RSS fetch with retry + exponential backoff."""

    for attempt in range(retry_attempts + 1):
        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(_fetch_via_gnews_sync, category, max_results),
                timeout=20.0,
            )
            if raw:
                return [_parse_rss_item(item) for item in raw if item.get("url")]
            # Empty response could mean rate-limited — retry once
            if attempt < retry_attempts:
                wait = 3.0 * (2 ** attempt) + random.uniform(0, 1)
                logger.debug("[trends.source] %s: empty RSS, retrying in %.1fs", category, wait)
                await asyncio.sleep(wait)
        except Exception as exc:
            err_str = str(exc).lower()
            is_rate_limited = any(s in err_str for s in ("429", "rate", "too many"))
            if attempt < retry_attempts:
                wait = (4.0 if is_rate_limited else 2.0) * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(
                    "[trends.source] %s: %s (attempt %d), retrying in %.1fs",
                    category, "rate-limited" if is_rate_limited else "error", attempt + 1, wait,
                )
                await asyncio.sleep(wait)
            else:
                logger.warning("[trends.source] %s: gave up after %d attempts: %s",
                               category, attempt + 1, str(exc)[:100])

    return []


def _parse_rss_item(item: dict[str, Any]) -> RawArticle:
    url = item.get("url", "")
    domain = urlparse(url).netloc.replace("www.", "") if url else "unknown"
    published_at = _parse_date(item.get("published date", ""))
    title = _strip_publisher_suffix(item.get("title", ""))
    publisher = item.get("publisher", {})
    source = publisher.get("title", domain) if isinstance(publisher, dict) else domain

    return RawArticle(
        title=title,
        description=item.get("description", ""),
        url=url,
        image_url=None,
        source=source,
        domain=domain,
        published_at=published_at,
    )


def _strip_publisher_suffix(title: str) -> str:
    return re.sub(r"\s*-\s*[^-]+$", "", title).strip() or title


def _parse_date(raw: str) -> datetime:
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return datetime.now()


# ──────────────────────────────────────────────────────────────────
#  FALLBACK: GNews API (only used when RSS fails)
# ──────────────────────────────────────────────────────────────────

GNEWS_API_BASE = "https://gnews.io/api/v4"


async def fetch_via_api(
    category: str,
    api_key: str,
    max_results: int = 10,
) -> list[RawArticle]:
    if not api_key:
        return []

    api_categories = {
        "technology": "technology", "business": "business", "health": "health",
        "science": "science", "sports": "sports", "entertainment": "entertainment",
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
            if resp.status_code == 429:
                logger.warning("[trends.source] API quota exhausted, stopping fallback")
                return []
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("[trends.source] API failed for %s: %s", category, str(exc)[:100])
        return []

    return [_parse_api_article(a) for a in data.get("articles", [])]


def _parse_api_article(item: dict[str, Any]) -> RawArticle:
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
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.now()


# ──────────────────────────────────────────────────────────────────
#  Public: try RSS, fall back to API only if it succeeded recently
# ──────────────────────────────────────────────────────────────────

async def fetch_category(
    category: str,
    api_key: str | None = None,
    max_results: int = 20,
) -> list[RawArticle]:
    """RSS first. API fallback only if it's likely to work."""
    articles = await fetch_via_rss(category, max_results)
    if articles:
        logger.info("[trends.source] %s: %d articles via RSS", category, len(articles))
        return articles

    if api_key:
        articles = await fetch_via_api(category, api_key, max_results)
        if articles:
            logger.info("[trends.source] %s: %d articles via API", category, len(articles))
        return articles

    return []