"""
Search Pipeline — async web search + content extraction in one pass.

Replaces the old three-file split (web_search / keyword_gen / content_extractor)
with a single pipeline class.

Architecture (inspired by Perplexity's multi-stage retrieval):

    parallel DDG queries
        → deduplicate by URL
        → domain diversity cap
        → concurrent page fetch + extraction
        → quality filter (min content length)
        → ordered results

Design decisions:
- Trust DDG's native ranking instead of manual scoring heuristics.
- Domain diversity (max N per domain) prevents source concentration.
- trafilatura → BeautifulSoup fallback for content extraction.
- Entire pipeline is async; DDG's sync API runs in a thread pool.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS

try:
    from langsmith import traceable
except ImportError:                       # langsmith optional at dev time
    def traceable(**kw):                  # type: ignore[misc]
        return lambda fn: fn

try:
    import trafilatura
except ImportError:
    trafilatura = None                    # graceful degradation → BS4 only

logger = logging.getLogger(__name__)

# ── Internal data object ──────────────────────────────────────

@dataclass
class SearchResult:
    """
    Internal result flowing through the pipeline.

    Converted to state-compatible TypedDicts in agent.py so that
    search.py stays decoupled from the shared MemoryState schema.
    """
    url: str
    title: str
    snippet: str
    domain: str
    rank: int           # DDG's original position — our primary relevance signal
    query: str
    text_content: str = ""
    text_length: int = 0
    image_url: str | None = None


# ── Pipeline ──────────────────────────────────────────────────

class SearchPipeline:
    """
    Async search-and-extract pipeline.

    Usage::

        pipeline = SearchPipeline()
        results  = await pipeline.run(["async python", "asyncio fastapi"])
        for r in results:
            print(r.title, r.text_length)
    """

    def __init__(
        self,
        results_per_query: int = 5,
        max_pages_to_fetch: int = 5,
        max_domain_hits: int = 2,
        min_content_length: int = 200,
        max_content_chars: int = 10_000,
        fetch_timeout: float = 12.0,
        concurrency: int = 4,
    ) -> None:
        self.results_per_query = results_per_query
        self.max_pages = max_pages_to_fetch
        self.max_domain_hits = max_domain_hits
        self.min_content_length = min_content_length
        self.max_content_chars = max_content_chars
        self.fetch_timeout = fetch_timeout
        self._sem = asyncio.Semaphore(concurrency)
        self._headers = {
            "User-Agent": "CupidResearch/1.0",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

    # ── Public entry point ────────────────────────────────────

    @traceable(name="research.search_pipeline")
    async def run(self, queries: list[str]) -> list[SearchResult]:
        """
        Execute full pipeline.

        Returns results ordered by original DDG rank, filtered for
        content quality and domain diversity.
        """
        # 1 — Parallel search across all queries
        raw = await self._search_all(queries)
        logger.debug("[search] raw results: %d", len(raw))

        # 2 — Deduplicate by normalized URL, keep first seen (highest rank)
        seen: set[str] = set()
        deduped: list[SearchResult] = []
        for r in raw:
            key = r.url.rstrip("/").lower()
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        # 3 — Domain diversity cap
        domain_counts: dict[str, int] = {}
        diverse: list[SearchResult] = []
        for r in deduped:
            count = domain_counts.get(r.domain, 0)
            if count < self.max_domain_hits:
                diverse.append(r)
                domain_counts[r.domain] = count + 1

        # 4 — Fetch + extract content from top candidates
        candidates = diverse[: self.max_pages]
        await self._extract_all(candidates)

        # 5 — Drop pages where extraction failed or content is too thin
        results = [r for r in candidates if r.text_length >= self.min_content_length]
        logger.debug("[search] final results: %d", len(results))
        return results

    # ── DDG search ────────────────────────────────────────────

    async def _search_all(self, queries: list[str]) -> list[SearchResult]:
        """Fan-out all queries concurrently."""
        tasks = [self._search_one(q) for q in queries]
        batches = await asyncio.gather(*tasks, return_exceptions=True)

        combined: list[SearchResult] = []
        for batch in batches:
            if isinstance(batch, list):
                combined.extend(batch)
        return combined

    async def _search_one(self, query: str) -> list[SearchResult]:
        """
        Run a single DDG text search in a thread pool.

        duckduckgo-search v6+ is sync-only — asyncio.to_thread()
        keeps the event loop responsive.
        """
        def _sync() -> list[dict]:
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=self.results_per_query))

        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(_sync),
                timeout=15.0,
            )
        except Exception as exc:
            logger.warning("[search] query=%s failed: %s", query, exc)
            return []

        results: list[SearchResult] = []
        for rank, item in enumerate(raw):
            url = (item.get("href") or "").strip()
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
        ) as client:
            tasks = [self._extract_one(client, r) for r in results]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _extract_one(
        self, client: httpx.AsyncClient, result: SearchResult,
    ) -> None:
        """Fetch a single page and parse its content into the result object."""
        async with self._sem:
            try:
                resp = await client.get(result.url)
                resp.raise_for_status()
                ct = resp.headers.get("content-type", "")
                if "html" not in ct and "text" not in ct:
                    return
                html = resp.text
            except Exception:
                return

            title, text, image = _parse_html(html, result.url)
            if title:
                result.title = title
            result.text_content = text[: self.max_content_chars]
            result.text_length = len(result.text_content)
            result.image_url = image


# ── HTML parsing (module-level, stateless) ────────────────────

def _parse_html(html: str, url: str) -> tuple[str, str, str | None]:
    """
    Extract (title, body_text, og_image) from raw HTML.

    Strategy: trafilatura first (best for articles), BeautifulSoup fallback.
    """
    if trafilatura is not None:
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
        if text:
            soup = BeautifulSoup(html, "html.parser")
            return _title(soup), _clean(text), _og_image(soup, url)

    # Fallback — manual paragraph extraction
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("script,style,nav,header,footer,aside,iframe"):
        tag.decompose()

    paragraphs = [
        _clean(p.get_text(" ", strip=True))
        for p in soup.select("article p, main p, .content p, p")
        if len(p.get_text(strip=True)) > 40
    ]
    return _title(soup), "\n\n".join(paragraphs), _og_image(soup, url)


def _title(soup: BeautifulSoup) -> str:
    """og:title → <title> → first <h1>."""
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return _clean(str(og["content"]))
    if soup.title and soup.title.string:
        return _clean(soup.title.string)
    h1 = soup.find("h1")
    return _clean(h1.get_text(strip=True)) if h1 else ""


def _og_image(soup: BeautifulSoup, base_url: str) -> str | None:
    """First usable image: og:image → article img."""
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
    """Normalize whitespace and decode HTML entities."""
    return re.sub(r"\s+", " ", unescape(text)).strip()