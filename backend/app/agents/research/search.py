"""
Search Pipeline — async web search + content extraction in one pass.

Architecture (inspired by Perplexity's multi-stage retrieval):

    dedupe queries
        → parallel DDG searches (with retry + backoff)
        → deduplicate results by URL
        → concurrent page fetch + extraction
        → content-quality filter + domain diversity
        → ranked results

Design decisions:
- DDG rate-limiting is real — retry with exponential backoff + jitter.
- Domain diversity applied *after* extraction so dead pages don't eat quota.
- Realistic Chrome User-Agent to avoid 403 from CF-protected sites.
- trafilatura for content extraction, BS4 only as true fallback.
- Entire pipeline is async; DDG's sync API runs in a thread pool.
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS

try:
    from langsmith import traceable
except ImportError:
    def traceable(**kw):  # type: ignore[misc]
        return lambda fn: fn

try:
    import trafilatura
except ImportError:
    trafilatura = None

logger = logging.getLogger(__name__)

# Realistic browser UA — stops 403s from Cloudflare-protected sites
_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


# ── Niche-specific domain authority map ──────────────────────────
#
# Each entry is (substring-matcher -> bonus). We match by suffix or
# substring on the hostname. Keys are lowercase.
#
# Why a map?  Generic ranking (.gov / .edu) is fine for academic topics
# but buries the sources that actually matter for creator niches
# (eg. for AI: huggingface, openai blog; for fitness: stronger by science).

_NICHE_DOMAIN_MAP: dict[str, dict[str, float]] = {
    "ai/ml": {
        "arxiv.org": 0.30, "huggingface.co": 0.25, "openai.com": 0.22,
        "anthropic.com": 0.22, "deepmind.com": 0.22, "ai.google": 0.20,
        "mlops.community": 0.15, "paperswithcode.com": 0.20,
        "towardsdatascience.com": 0.12, "distill.pub": 0.20,
        "blog.google": 0.10, "microsoft.com/en-us/research": 0.18,
    },
    "software": {
        "github.com": 0.25, "stackoverflow.com": 0.20, "dev.to": 0.12,
        "martinfowler.com": 0.22, "developer.mozilla.org": 0.22,
        "docs.python.org": 0.20, "realpython.com": 0.15,
        "engineering.atspotify.com": 0.15, "netflixtechblog.com": 0.15,
        "aws.amazon.com/blogs": 0.12, "cloud.google.com/blog": 0.12,
    },
    "fitness": {
        "pubmed.ncbi.nlm.nih.gov": 0.25, "strongerbyscience.com": 0.25,
        "examine.com": 0.22, "nsca.com": 0.18, "acefitness.org": 0.15,
        "mensjournal.com": 0.10, "t-nation.com": 0.10,
    },
    "finance": {
        "bloomberg.com": 0.22, "reuters.com": 0.22, "ft.com": 0.20,
        "wsj.com": 0.18, "sec.gov": 0.25, "imf.org": 0.18,
        "federalreserve.gov": 0.22, "investopedia.com": 0.12,
        "cnbc.com": 0.10, "morningstar.com": 0.15, "economist.com": 0.18,
    },
    "marketing": {
        "hubspot.com": 0.18, "backlinko.com": 0.18, "ahrefs.com": 0.18,
        "moz.com": 0.15, "semrush.com": 0.15, "neilpatel.com": 0.10,
        "searchengineland.com": 0.15, "marketingweek.com": 0.12,
        "marketingcharts.com": 0.15, "hbr.org": 0.18,
    },
    "health": {
        "pubmed.ncbi.nlm.nih.gov": 0.28, "who.int": 0.25, "cdc.gov": 0.25,
        "nih.gov": 0.25, "mayoclinic.org": 0.20, "health.harvard.edu": 0.20,
        "nejm.org": 0.25, "thelancet.com": 0.22, "bmj.com": 0.20,
    },
    "creator": {
        "youtube.com/creators": 0.18, "creatoreconomy.so": 0.18,
        "tubefilter.com": 0.15, "socialmediatoday.com": 0.15,
        "buffer.com/resources": 0.15, "later.com/blog": 0.12,
        "thinkmedia.com": 0.10, "patreon.com/blog": 0.12,
    },
    "crypto": {
        "coindesk.com": 0.20, "cointelegraph.com": 0.15, "messari.io": 0.22,
        "a16zcrypto.com": 0.20, "defillama.com": 0.22, "ethereum.org": 0.22,
        "bitcoin.org": 0.20, "glassnode.com": 0.18,
    },
    "design": {
        "figma.com/blog": 0.18, "smashingmagazine.com": 0.20,
        "nngroup.com": 0.25, "uxdesign.cc": 0.12, "behance.net": 0.10,
        "dribbble.com": 0.10, "abduzeedo.com": 0.10,
    },
}


def _resolve_niche_key(niche: str) -> str | None:
    """Map a free-form niche string onto one of _NICHE_DOMAIN_MAP's keys."""
    n = niche.lower()
    if any(k in n for k in ("ai", "ml", "machine learning", "data scien", "llm", "genai")):
        return "ai/ml"
    if any(k in n for k in ("software", "web dev", "programming", "coding", "developer", "devops")):
        return "software"
    if any(k in n for k in ("fitness", "gym", "workout", "exercise", "strength", "bodybuilding")):
        return "fitness"
    if any(k in n for k in ("finance", "invest", "stock", "trading", "economy", "wealth")):
        return "finance"
    if any(k in n for k in ("crypto", "web3", "blockchain", "bitcoin", "defi")):
        return "crypto"
    if any(k in n for k in ("market", "growth", "seo", "ads", "brand", "copywrit")):
        return "marketing"
    if any(k in n for k in ("health", "wellness", "nutrition", "mental", "medical", "medicine")):
        return "health"
    if any(k in n for k in ("creator", "youtube", "podcast", "influencer", "content creat")):
        return "creator"
    if any(k in n for k in ("design", "ux", "ui", "product design")):
        return "design"
    return None


# Regional TLD/domain hints — boost pages from the user's target country.
# Two-letter ISO TLDs get a fixed boost; a handful of well-known publishers
# get an extra edge because their country-of-record is not obvious from the TLD.
_COUNTRY_TLD: dict[str, str] = {
    "india": ".in",       "united kingdom": ".uk",   "uk": ".uk",
    "germany": ".de",     "france": ".fr",           "spain": ".es",
    "italy": ".it",        "netherlands": ".nl",     "japan": ".jp",
    "south korea": ".kr",  "korea": ".kr",           "china": ".cn",
    "brazil": ".br",       "mexico": ".mx",          "canada": ".ca",
    "australia": ".au",    "new zealand": ".nz",     "singapore": ".sg",
    "indonesia": ".id",    "united arab emirates": ".ae",
    "uae": ".ae",          "saudi arabia": ".sa",    "russia": ".ru",
    "south africa": ".za",
}

_COUNTRY_PUBLISHER_BONUS: dict[str, set[str]] = {
    "india":          {"economictimes.indiatimes.com", "livemint.com",
                       "thehindu.com", "moneycontrol.com", "indianexpress.com"},
    "united states":  {"nytimes.com", "washingtonpost.com"},
    "united kingdom": {"bbc.co.uk", "theguardian.com", "ft.com"},
}


def _region_bonus(domain: str, country: str | None) -> float:
    """Extra relevance for hosts matching the creator's target country."""
    if not country:
        return 0.0
    c = country.strip().lower()
    tld = _COUNTRY_TLD.get(c)
    bonus = 0.0
    if tld and domain.endswith(tld):
        bonus += 0.18
    for pub in _COUNTRY_PUBLISHER_BONUS.get(c, set()):
        if domain.endswith(pub):
            bonus = max(bonus, 0.18)
    return bonus


def _niche_bonus(domain: str, niche_key: str | None) -> float:
    """Extra relevance for hosts known to be authoritative in this niche."""
    if not niche_key:
        return 0.0
    domain_map = _NICHE_DOMAIN_MAP.get(niche_key, {})
    best = 0.0
    for host_substr, bonus in domain_map.items():
        if host_substr in domain and bonus > best:
            best = bonus
    return best


# ── Internal data object ──────────────────────────────────────

@dataclass
class SearchResult:
    """Internal result flowing through the pipeline."""
    url: str
    title: str
    snippet: str
    domain: str
    rank: int           # DDG's original position — primary relevance signal
    query: str
    text_content: str = ""
    text_length: int = 0     # word count, not char count
    image_url: str | None = None
    score: float = 0.0       # rank-based composite, computed at the end


# ── Pipeline ──────────────────────────────────────────────────

class SearchPipeline:
    """
    Async search-and-extract pipeline.

    Usage::

        pipeline = SearchPipeline()
        results  = await pipeline.run(["async python", "asyncio fastapi"])
    """

    def __init__(
        self,
        results_per_query: int = 5,
        max_pages_to_fetch: int = 12,
        max_domain_hits: int = 2,
        min_word_count: int = 80,
        max_content_chars: int = 10_000,
        fetch_timeout: float = 12.0,
        overall_budget: float = 30.0,
        fetch_concurrency: int = 8,
        search_concurrency: int = 3,
        search_retries: int = 2,
    ) -> None:
        self.results_per_query = results_per_query
        self.max_pages = max_pages_to_fetch
        self.max_domain_hits = max_domain_hits
        self.min_word_count = min_word_count
        self.max_content_chars = max_content_chars
        self.fetch_timeout = fetch_timeout
        self.overall_budget = overall_budget
        self.search_retries = search_retries
        self._fetch_sem = asyncio.Semaphore(fetch_concurrency)
        self._search_sem = asyncio.Semaphore(search_concurrency)
        self._headers = {
            "User-Agent": _CHROME_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }

    # ── Public entry point ────────────────────────────────────

    @traceable(name="research.search_pipeline")
    async def run(
        self,
        queries: list[str],
        persona: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        Execute full pipeline.

        Returns results ordered by composite score, filtered for
        content quality and domain diversity. Persona (niche + country)
        steers which domains get a relevance boost.
        """
        try:
            return await asyncio.wait_for(
                self._run_inner(queries, persona or {}),
                timeout=self.overall_budget,
            )
        except asyncio.TimeoutError:
            logger.warning("[search] overall budget %.1fs exceeded", self.overall_budget)
            return []

    async def _run_inner(
        self,
        queries: list[str],
        persona: dict[str, Any],
    ) -> list[SearchResult]:
        queries = _dedupe_queries(queries)
        logger.debug("[search] queries after dedupe: %d", len(queries))

        # 1 — Parallel search across all queries
        raw = await self._search_all(queries)
        logger.debug("[search] raw results: %d", len(raw))
        if not raw:
            return []

        # 2 — Deduplicate by normalized URL, keep first seen (highest rank)
        seen: set[str] = set()
        deduped: list[SearchResult] = []
        for r in raw:
            key = _normalize_url(r.url)
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        # 3 — Fetch more candidates than needed (domain cap drops some later)
        candidates = deduped[: self.max_pages * 2]
        await self._extract_all(candidates)

        # 4 — Keep only pages with real content
        with_content = [r for r in candidates if r.text_length >= self.min_word_count]
        logger.debug("[search] pages with content: %d", len(with_content))

        # 5 — Domain diversity (applied AFTER extraction — dead pages don't eat quota)
        domain_counts: dict[str, int] = {}
        diverse: list[SearchResult] = []
        for r in with_content:
            if domain_counts.get(r.domain, 0) < self.max_domain_hits:
                diverse.append(r)
                domain_counts[r.domain] = domain_counts.get(r.domain, 0) + 1

        # 6 — Composite score + final sort (persona-aware boosts)
        niche_key = _resolve_niche_key(str(persona.get("content_niche") or ""))
        country = persona.get("target_country")
        for r in diverse:
            r.score = _compute_score(r, niche_key, country)
        diverse.sort(key=lambda r: r.score, reverse=True)

        results = diverse[: self.max_pages]
        logger.info(
            "[search] final: %d pages across %d domains",
            len(results), len({r.domain for r in results}),
        )
        return results

    # ── DDG search with retry ─────────────────────────────────

    async def _search_all(self, queries: list[str]) -> list[SearchResult]:
        tasks = [self._search_one(q) for q in queries]
        batches = await asyncio.gather(*tasks, return_exceptions=True)

        combined: list[SearchResult] = []
        for batch in batches:
            if isinstance(batch, list):
                combined.extend(batch)
        return combined

    async def _search_one(self, query: str) -> list[SearchResult]:
        """Run a single DDG text search in a thread pool with retry + backoff."""

        def _sync() -> list[dict]:
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=self.results_per_query))

        async with self._search_sem:
            for attempt in range(self.search_retries + 1):
                try:
                    raw = await asyncio.wait_for(
                        asyncio.to_thread(_sync),
                        timeout=15.0,
                    )
                    return self._format_results(raw, query)

                except Exception as exc:
                    err_str = str(exc).lower()
                    is_rate_limit = (
                        "ratelimit" in err_str
                        or "429" in err_str
                        or "too many requests" in err_str
                    )
                    is_last_attempt = attempt >= self.search_retries

                    if is_last_attempt:
                        logger.warning(
                            "[search] query=%r gave up after %d attempts: %s",
                            query, attempt + 1, str(exc)[:120],
                        )
                        return []

                    # Exponential backoff with jitter; longer for rate limits
                    base = 3.0 if is_rate_limit else 1.0
                    delay = base * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.debug(
                        "[search] query=%r %s, retrying in %.1fs",
                        query,
                        "rate-limited" if is_rate_limit else "failed",
                        delay,
                    )
                    await asyncio.sleep(delay)

            return []

    def _format_results(self, raw: list[dict], query: str) -> list[SearchResult]:
        results: list[SearchResult] = []
        for rank, item in enumerate(raw):
            url = (item.get("href") or item.get("url") or "").strip()
            title = (item.get("title") or "").strip()
            if not url or not title:
                continue
            results.append(SearchResult(
                url=url,
                title=title,
                snippet=(item.get("body") or "").strip(),
                domain=urlparse(url).netloc.replace("www.", ""),
                rank=rank,
                query=query,
            ))
        return results

    # ── Content extraction ────────────────────────────────────

    async def _extract_all(self, results: list[SearchResult]) -> None:
        """Fetch + extract page content concurrently, mutating results in place."""
        async with httpx.AsyncClient(
            headers=self._headers,
            timeout=httpx.Timeout(
                connect=5.0, read=self.fetch_timeout, write=10.0, pool=5.0,
            ),
            follow_redirects=True,
            http2=False,  # some sites behave badly with h2
        ) as client:
            tasks = [self._extract_one(client, r) for r in results]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _extract_one(
        self, client: httpx.AsyncClient, result: SearchResult,
    ) -> None:
        async with self._fetch_sem:
            try:
                resp = await client.get(result.url)
                resp.raise_for_status()
                if "html" not in resp.headers.get("content-type", "").lower():
                    logger.debug("[extract] %s: non-html content", result.domain)
                    self._apply_snippet_fallback(result)
                    return
                html = resp.text
            except httpx.HTTPStatusError as exc:
                logger.debug("[extract] %s: http %s", result.domain, exc.response.status_code)
                self._apply_snippet_fallback(result)
                return
            except Exception as exc:
                logger.debug("[extract] %s: %s", result.domain, type(exc).__name__)
                self._apply_snippet_fallback(result)
                return

        title, text, image = _parse_html(html, result.url)
        if title:
            result.title = title
        text = _smart_truncate(text, self.max_content_chars)
        result.text_content = text
        result.text_length = len(text.split())
        result.image_url = image

        if result.text_length < self.min_word_count:
            self._apply_snippet_fallback(result)

    def _apply_snippet_fallback(self, result: SearchResult) -> None:
        """When extraction fails or is too thin, use the DDG snippet."""
        if result.snippet and not result.text_content:
            result.text_content = result.snippet
            result.text_length = len(result.snippet.split())


# ── Helpers ────────────────────────────────────────────────────

def _dedupe_queries(queries: list[str]) -> list[str]:
    """Remove near-duplicate queries (case + whitespace normalized)."""
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        key = " ".join(q.lower().split())
        if key and key not in seen:
            seen.add(key)
            out.append(q)
    return out


def _normalize_url(url: str) -> str:
    """Normalize for dedup: strip trailing slash, lowercase host, drop fragments."""
    try:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc.lower()}{p.path.rstrip('/')}".lower()
    except Exception:
        return url.rstrip("/").lower()


def _compute_score(
    r: SearchResult,
    niche_key: str | None = None,
    country: str | None = None,
) -> float:
    """
    Composite relevance score:
    - Base:      inverse of DDG rank (1.0 for rank 0, 0.5 for rank 1, ...)
    - Depth:     log-scaled content length (word count)
    - Authority: generic TLD authority (.gov / .edu / .org / well-knowns)
    - Niche:     niche-specific domain map (AI-ML → arxiv/HF, finance → SEC, …)
    - Region:    target-country TLD or named publisher
    """
    import math
    base = 1.0 / (r.rank + 1)
    depth = min(math.log(max(r.text_length, 1)) / 10, 0.5)

    domain = r.domain
    if domain.endswith((".gov", ".edu")):
        authority = 0.30
    elif domain.endswith(".org"):
        authority = 0.15
    elif any(h in domain for h in (
        "github.com", "arxiv.org", "stackoverflow.com",
        "docs.python.org", "mozilla.org", "wikipedia.org",
    )):
        authority = 0.20
    else:
        authority = 0.0

    niche = _niche_bonus(domain, niche_key)
    region = _region_bonus(domain, country)

    return base + depth + authority + niche + region


def _smart_truncate(text: str, max_chars: int) -> str:
    """Cut at sentence boundary within budget, not mid-word."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    # Prefer ending at sentence boundary
    last_period = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if last_period > max_chars * 0.7:
        return cut[: last_period + 1]
    # Fallback: last whitespace
    last_space = cut.rfind(" ")
    return cut[:last_space] if last_space > 0 else cut


# ── HTML parsing ──────────────────────────────────────────────

def _parse_html(html: str, url: str) -> tuple[str, str, str | None]:
    """Extract (title, body_text, og_image) from raw HTML."""
    if trafilatura is not None:
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        if text:
            # Trafilatura gave us clean text — one BS4 pass for metadata
            soup = BeautifulSoup(html, "html.parser")
            return _title(soup), _clean(text), _og_image(soup, url)

    # Fallback — manual paragraph extraction
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("script,style,nav,header,footer,aside,iframe,noscript"):
        tag.decompose()

    paragraphs = [
        _clean(p.get_text(" ", strip=True))
        for p in soup.select("article p, main p, .content p, p")
        if len(p.get_text(strip=True)) > 40
    ]
    return _title(soup), "\n\n".join(paragraphs), _og_image(soup, url)


def _title(soup: BeautifulSoup) -> str:
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return _clean(str(og["content"]))
    if soup.title and soup.title.string:
        return _clean(soup.title.string)
    h1 = soup.find("h1")
    return _clean(h1.get_text(strip=True)) if h1 else ""


def _og_image(soup: BeautifulSoup, base_url: str) -> str | None:
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return str(og["content"])
    for img in soup.select("article img, main img, .content img"):
        src = img.get("src") or img.get("data-src")
        if src:
            abs_url = urljoin(base_url, str(src))
            if "pixel" not in abs_url.lower() and "tracking" not in abs_url.lower():
                return abs_url
    return None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text)).strip()