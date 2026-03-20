"""
Cupid Research Agent

A fully asynchronous research agent that:
- generates search keywords from a user topic
- searches the web concurrently
- fetches and extracts page content concurrently
- prints a clean, colorful terminal report
- writes a markdown report to disk

This version is intentionally kept in a single file for learning,
but the design is modular enough to split into services later.

Install:
    pip install httpx beautifulsoup4 rich trafilatura

Run:
    python cupid_research_agent.py "python decorators"
"""

from __future__ import annotations

import asyncio
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from html import unescape
from typing import List
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table

try:
    import trafilatura
except Exception:
    trafilatura = None


console = Console()


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "how", "i", "in", "is", "it", "of", "on", "or", "so", "the",
    "this", "that", "to", "was", "what", "when", "where", "which",
    "who", "why", "with", "you", "your", "we", "can", "will",
    "do", "does", "did", "about", "into", "over", "under", "best",
    "guide", "tips", "examples", "use", "using", "vs", "new", "latest",
}


@dataclass
class ResearchConfig:
    """Configuration for the research agent."""

    topic: str
    max_queries: int = 6
    results_per_query: int = 5
    pages_to_fetch: int = 8
    search_concurrency: int = 3
    fetch_concurrency: int = 4
    retries: int = 3
    backoff_base: float = 0.8
    timeout: httpx.Timeout = field(
        default_factory=lambda: httpx.Timeout(connect=5.0, read=12.0, write=10.0, pool=5.0)
    )
    limits: httpx.Limits = field(
        default_factory=lambda: httpx.Limits(max_connections=20, max_keepalive_connections=10)
    )
    headers: dict[str, str] = field(
        default_factory=lambda: {
            "User-Agent": "CupidResearchAgent/1.0 (+https://example.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        }
    )


@dataclass
class SearchResult:
    """Single search result item returned from the web search stage."""

    query: str
    title: str
    url: str
    snippet: str
    domain: str
    score: float


@dataclass
class PageNotes:
    """Extracted notes from one web page."""

    url: str
    title: str
    summary: str
    headings: list[str]
    key_phrases: list[str]
    text_length: int


@dataclass
class ResearchReport:
    """Final structured result returned by the agent."""

    topic: str
    generated_keywords: list[str]
    queries: list[str]
    top_results: list[SearchResult]
    page_notes: list[PageNotes]
    stage_timings: dict[str, float]

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append(f"# Research Report: {self.topic}")
        lines.append("")
        lines.append("## Generated keyword ideas")
        for keyword in self.generated_keywords:
            lines.append(f"- {keyword}")
        lines.append("")
        lines.append("## Queries used")
        for query in self.queries:
            lines.append(f"- {query}")
        lines.append("")
        lines.append("## Top sources")
        for idx, result in enumerate(self.top_results, start=1):
            lines.append(f"### [{idx}] {result.title}")
            lines.append(f"- URL: {result.url}")
            lines.append(f"- Domain: {result.domain}")
            lines.append(f"- Score: {result.score:.3f}")
            if result.snippet:
                lines.append(f"- Snippet: {result.snippet}")
            lines.append("")
        lines.append("## Page notes")
        for idx, note in enumerate(self.page_notes, start=1):
            lines.append(f"### [{idx}] {note.title}")
            lines.append(f"- URL: {note.url}")
            lines.append(f"- Text length: {note.text_length}")
            lines.append(f"- Summary: {note.summary}")
            if note.headings:
                lines.append(f"- Headings: {', '.join(note.headings[:6])}")
            if note.key_phrases:
                lines.append(f"- Key phrases: {', '.join(note.key_phrases[:8])}")
            lines.append("")
        lines.append("## Stage timings")
        for stage, seconds in self.stage_timings.items():
            lines.append(f"- {stage}: {seconds:.3f}s")
        return "\n".join(lines)


class KeywordPlanner:
    """Generate search queries from the user topic."""

    def __init__(self, topic: str) -> None:
        self.topic = topic.strip()
        self.tokens = self._tokenize(self.topic)

    def _tokenize(self, text: str) -> list[str]:
        raw = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-\+\.]*", text.lower())
        return [token for token in raw if token not in STOPWORDS and len(token) > 1]

    def generate(self) -> list[str]:
        if not self.topic:
            return []

        core_terms = self._core_terms()
        phrases: list[str] = [self.topic]

        if core_terms and " ".join(core_terms[:4]).strip().lower() != self.topic.lower():
            phrases.append(" ".join(core_terms[:4]))

        suffixes = [
            "best practices",
            "latest trends",
            "examples",
            "tools",
            "guide",
            "research",
            "case studies",
        ]

        for suffix in suffixes:
            phrases.append(f"{self.topic} {suffix}")

        if len(core_terms) >= 2:
            bigrams = [f"{core_terms[i]} {core_terms[i + 1]}" for i in range(len(core_terms) - 1)]
            phrases.extend(bigrams[:4])

        if core_terms:
            phrases.extend([f"{term} research" for term in core_terms[:4]])
            phrases.extend([f"{term} trends" for term in core_terms[:4]])
            phrases.extend([f"{term} tools" for term in core_terms[:4]])

        unique: list[str] = []
        seen = set()
        for query in phrases:
            normalized = query.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique.append(query.strip())

        return unique[:8]

    def _core_terms(self) -> list[str]:
        freq = Counter(self.tokens)
        ordered = sorted(freq.items(), key=lambda item: (-len(item[0]), -item[1], item[0]))
        return [term for term, _ in ordered]


class ResearchAgent:
    """Async research agent that searches the web and extracts page notes."""

    SEARCH_URL = "https://html.duckduckgo.com/html/"

    def __init__(self, config: ResearchConfig) -> None:
        self.config = config
        self.planner = KeywordPlanner(config.topic)
        self.search_semaphore = asyncio.Semaphore(config.search_concurrency)
        self.fetch_semaphore = asyncio.Semaphore(config.fetch_concurrency)

    async def run(self) -> ResearchReport:
        start_time = time.perf_counter()
        stage_timings: dict[str, float] = {}

        # Keyword planning happens first so the agent has multiple search angles.
        query_start = time.perf_counter()
        queries = self.planner.generate()[: self.config.max_queries]
        stage_timings["keyword_planning"] = time.perf_counter() - query_start

        async with httpx.AsyncClient(
            headers=self.config.headers,
            timeout=self.config.timeout,
            limits=self.config.limits,
            follow_redirects=True,
        ) as client:
            # Search stage: execute multiple search queries concurrently.
            search_start = time.perf_counter()
            search_batches = await asyncio.gather(
                *[self._search_query(client, query) for query in queries],
                return_exceptions=True,
            )
            stage_timings["search"] = time.perf_counter() - search_start

            all_results: list[SearchResult] = []
            for batch in search_batches:
                if isinstance(batch, Exception):
                    continue
                all_results.extend(batch)

            top_results = self._deduplicate_and_rank(all_results)[: self.config.pages_to_fetch]

            # Fetch stage: load the selected pages concurrently.
            fetch_start = time.perf_counter()
            page_batches = await asyncio.gather(
                *[self._fetch_and_extract(client, result.url) for result in top_results],
                return_exceptions=True,
            )
            stage_timings["page_fetch_and_extract"] = time.perf_counter() - fetch_start

        page_notes: list[PageNotes] = []
        for item in page_batches:
            if isinstance(item, PageNotes):
                page_notes.append(item)

        stage_timings["total"] = time.perf_counter() - start_time

        return ResearchReport(
            topic=self.config.topic,
            generated_keywords=queries,
            queries=queries,
            top_results=top_results,
            page_notes=page_notes,
            stage_timings=stage_timings,
        )

    async def _search_query(self, client: httpx.AsyncClient, query: str) -> list[SearchResult]:
        async with self.search_semaphore:
            html = await self._get_text(client, self.SEARCH_URL, params={"q": query})
            return self._parse_duckduckgo_results(html, query)

    async def _fetch_and_extract(self, client: httpx.AsyncClient, url: str) -> PageNotes:
        async with self.fetch_semaphore:
            html = await self._get_text(client, url)
            return self._extract_page_notes(html, url)

    async def _get_text(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: dict[str, str] | None = None,
    ) -> str:
        last_error: Exception | None = None

        for attempt in range(self.config.retries):
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "").lower()
                if "text" not in content_type and "html" not in content_type and "json" not in content_type:
                    raise ValueError(f"Unsupported content type: {content_type}")

                return response.text
            except Exception as exc:
                last_error = exc
                if attempt == self.config.retries - 1:
                    break
                await asyncio.sleep(self.config.backoff_base * (2 ** attempt))

        raise last_error or RuntimeError("Unknown network error")

    def _parse_duckduckgo_results(self, html: str, query: str) -> list[SearchResult]:
        soup = BeautifulSoup(html, "html.parser")
        items: list[SearchResult] = []
        query_terms = self._meaningful_terms(query)

        for result in soup.select("div.result"):
            anchor = result.select_one("a.result__a")
            if not anchor:
                continue

            title = self._clean_text(anchor.get_text(" ", strip=True))
            href = anchor.get("href", "")
            url = self._normalize_url(href)
            if not url:
                continue

            snippet_el = result.select_one("a.result__snippet, div.result__snippet")
            snippet = self._clean_text(snippet_el.get_text(" ", strip=True)) if snippet_el else ""
            domain = self._domain(url)
            score = self._score_result(query_terms, title, snippet, domain)

            items.append(
                SearchResult(
                    query=query,
                    title=title,
                    url=url,
                    snippet=snippet,
                    domain=domain,
                    score=score,
                )
            )

        return sorted(items, key=lambda item: item.score, reverse=True)[: self.config.results_per_query]

    def _extract_page_notes(self, html: str, url: str) -> PageNotes:
        title, summary, headings, text = self._extract_content(html)
        key_phrases = self._key_phrases(text)
        return PageNotes(
            url=url,
            title=title or self._domain(url),
            summary=summary,
            headings=headings,
            key_phrases=key_phrases,
            text_length=len(text),
        )

    def _extract_content(self, html: str) -> tuple[str, str, list[str], str]:
        if trafilatura is not None:
            extracted = trafilatura.extract(html, include_comments=False, include_tables=False)
            if extracted:
                text = self._clean_text(extracted)
                soup = BeautifulSoup(html, "html.parser")
                title = self._page_title(soup)
                headings = self._page_headings(soup)
                summary = self._summarize_text(text)
                return title, summary, headings, text

        soup = BeautifulSoup(html, "html.parser")
        title = self._page_title(soup)
        headings = self._page_headings(soup)
        paragraphs = [self._clean_text(p.get_text(" ", strip=True)) for p in soup.select("p")]
        text = "\n".join(paragraphs)
        summary = self._summarize_text(text)
        return title, summary, headings, text

    def _page_title(self, soup: BeautifulSoup) -> str:
        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title and og_title.get("content"):
            return self._clean_text(og_title["content"])
        if soup.title and soup.title.string:
            return self._clean_text(soup.title.string)
        return ""

    def _page_headings(self, soup: BeautifulSoup) -> list[str]:
        headings: list[str] = []
        for selector in ["h1", "h2", "h3"]:
            for tag in soup.select(selector)[:3]:
                text = self._clean_text(tag.get_text(" ", strip=True))
                if text and text not in headings:
                    headings.append(text)
        return headings

    def _summarize_text(self, text: str, max_sentences: int = 3) -> str:
        if not text.strip():
            return "No readable text extracted."
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        summary = " ".join(sentences[:max_sentences]).strip()
        return summary[:600]

    def _key_phrases(self, text: str, limit: int = 8) -> list[str]:
        tokens = self._meaningful_terms(text)
        if not tokens:
            return []
        counts = Counter(tokens)
        ranked = sorted(counts.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
        return [term for term, _ in ranked[:limit]]

    def _meaningful_terms(self, text: str) -> list[str]:
        terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-\+\.]*", text.lower())
        return [term for term in terms if term not in STOPWORDS and len(term) > 2]

    def _score_result(self, query_terms: list[str], title: str, snippet: str, domain: str) -> float:
        title_terms = set(self._meaningful_terms(title))
        snippet_terms = set(self._meaningful_terms(snippet))
        overlap_title = len(title_terms.intersection(query_terms))
        overlap_snippet = len(snippet_terms.intersection(query_terms))

        domain_bonus = 0.0
        if domain.endswith(".gov"):
            domain_bonus = 0.3
        elif domain.endswith(".edu"):
            domain_bonus = 0.25
        elif domain.endswith(".org"):
            domain_bonus = 0.15

        return float(overlap_title * 2.0 + overlap_snippet * 0.8 + domain_bonus)

    def _deduplicate_and_rank(self, results: list[SearchResult]) -> list[SearchResult]:
        best_by_url: dict[str, SearchResult] = {}

        for result in results:
            current = best_by_url.get(result.url)
            if current is None or result.score > current.score:
                best_by_url[result.url] = result

        return sorted(best_by_url.values(), key=lambda item: (-item.score, item.domain, item.title))

    def _normalize_url(self, href: str) -> str:
        if not href:
            return ""

        href = unescape(href)

        if href.startswith("//"):
            href = "https:" + href

        parsed = urlparse(href)

        if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
            qs = parse_qs(parsed.query)
            if "uddg" in qs and qs["uddg"]:
                return unquote(qs["uddg"][0])

        if parsed.scheme in {"http", "https"}:
            return href

        if href.startswith("/l/?"):
            qs = parse_qs(parsed.query)
            if "uddg" in qs and qs["uddg"]:
                return unquote(qs["uddg"][0])

        return href

    def _domain(self, url: str) -> str:
        return urlparse(url).netloc.replace("www.", "")

    def _clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", unescape(text)).strip()


def print_banner(topic: str) -> None:
    console.rule(f"[bold cyan]Cupid Research Agent — {topic}")


def print_keyword_section(keywords: list[str]) -> None:
    console.print(Panel.fit("\n".join(f"• {k}" for k in keywords), title="Generated Keyword Ideas", border_style="green"))


def print_top_results(results: list[SearchResult]) -> None:
    table = Table(title="Top Sources", show_lines=True)
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Title", style="bold white", overflow="fold")
    table.add_column("Domain", style="magenta", width=24)
    table.add_column("Score", style="yellow", justify="right", width=8)

    for idx, result in enumerate(results, start=1):
        table.add_row(
            str(idx),
            result.title,
            result.domain,
            f"{result.score:.2f}",
        )

    console.print(table)


def print_page_notes(notes: list[PageNotes]) -> None:
    console.print()
    console.rule("[bold cyan]Page Notes")

    for idx, note in enumerate(notes, start=1):
        body_lines = [
            f"[bold]URL:[/bold] {note.url}",
            f"[bold]Text length:[/bold] {note.text_length}",
            f"[bold]Summary:[/bold] {note.summary}",
        ]

        if note.headings:
            body_lines.append(f"[bold]Headings:[/bold] {', '.join(note.headings[:4])}")

        if note.key_phrases:
            body_lines.append(f"[bold]Key phrases:[/bold] {', '.join(note.key_phrases[:6])}")

        console.print(
            Panel(
                "\n".join(body_lines),
                title=f"{idx}. {note.title}",
                border_style="blue",
            )
        )


def print_timings(timings: dict[str, float]) -> None:
    table = Table(title="Timings", show_lines=True)
    table.add_column("Stage", style="cyan")
    table.add_column("Seconds", style="yellow", justify="right")

    for stage, value in timings.items():
        table.add_row(stage, f"{value:.3f}")

    console.print(table)


async def run(topic: str) -> ResearchReport:
    config = ResearchConfig(topic=topic)
    agent = ResearchAgent(config)
    return await agent.run()


def main() -> None:
    topic = " ".join(sys.argv[1:]).strip()
    if not topic:
        topic = input("Enter a research topic: ").strip()
    if not topic:
        raise SystemExit("No topic provided.")

    started = time.perf_counter()
    print_banner(topic)

    report = asyncio.run(run(topic))
    total_elapsed = time.perf_counter() - started

    print_keyword_section(report.generated_keywords)
    print_top_results(report.top_results)
    print_page_notes(report.page_notes)
    print_timings(report.stage_timings)

    console.print(
        Panel.fit(
            f"[bold magenta]Total wall time:[/bold magenta] {total_elapsed:.3f}s\n"
            f"[bold green]Markdown report written to:[/bold green] cupid_research_report.md",
            border_style="magenta",
            title="Run Summary",
        )
    )

    with open("cupid_research_report.md", "w", encoding="utf-8") as f:
        f.write(report.to_markdown())


if __name__ == "__main__":
    main()
