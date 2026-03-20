"""
Cupid Research Agent

Upgraded research agent with a more advanced pipeline.

Features
- Async web search
- Dynamic query generation using a local LLM
- Page scraping and cleaning
- Corpus chunking
- Hierarchical summarization

Model Strategy
Primary model: qwen2.5:3b
Fallback model: gemma2:2b

The agent communicates with a local inference server compatible with the
Ollama API. This allows running local models while keeping the code simple.

Install dependencies
pip install httpx beautifulsoup4 trafilatura rich

Install models (example using Ollama)
ollama pull qwen2.5:3b
ollama pull gemma2:2b

Run
python research_agent.py "python decorators"
"""

import asyncio
import json
import re
import sys
import time
from dataclasses import dataclass, field
from typing import List
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

try:
    import trafilatura
except Exception:
    trafilatura = None

console = Console()


@dataclass
class ResearchConfig:

    topic: str

    max_queries: int = 6
    results_per_query: int = 5
    pages_to_fetch: int = 8

    search_concurrency: int = 3
    fetch_concurrency: int = 4

    chunk_size: int = 2000

    timeout: httpx.Timeout = field(default_factory=lambda: httpx.Timeout(15.0))

    limits: httpx.Limits = field(
        default_factory=lambda: httpx.Limits(max_connections=20, max_keepalive_connections=10)
    )

    headers: dict = field(
        default_factory=lambda: {
            "User-Agent": "CupidResearchAgent/1.0",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )


class LLMEngine:

    def __init__(self):

        self.primary = "qwen2.5:3b"
        self.fallback = "gemma2:2b"

    async def generate_queries(self, topic: str) -> List[str]:

        prompt = f"""
You are a research planner.
Generate diverse web search queries for the topic.
Return JSON with format:
{{"queries": ["query1", "query2"]}}

Topic: {topic}
"""

        text = await self._call_model(prompt)

        try:
            parsed = json.loads(text)
            queries = parsed.get("queries", [])
            if queries:
                return queries
        except Exception:
            pass

        return [topic]

    async def summarize_chunk(self, topic: str, chunk: str) -> str:

        prompt = f"""
Summarize the following text about {topic}.
Focus only on the important technical or conceptual information.

Text:
{chunk}
"""

        return await self._call_model(prompt)

    async def synthesize(self, topic: str, summaries: List[str]) -> str:

        joined = "\n".join(summaries)

        prompt = f"""
Create a structured final explanation for the topic: {topic}

Use the following research notes:

{joined}
"""

        return await self._call_model(prompt)

    async def _call_model(self, prompt: str):

        payload = {
            "model": self.primary,
            "prompt": prompt,
            "stream": False,
        }

        try:

            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post("http://localhost:11434/api/generate", json=payload)
                r.raise_for_status()
                return r.json()["response"]

        except Exception:

            payload["model"] = self.fallback

            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post("http://localhost:11434/api/generate", json=payload)
                r.raise_for_status()
                return r.json()["response"]


class SearchResult:

    def __init__(self, title, url, snippet, domain, score):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.domain = domain
        self.score = score


class ResearchAgent:

    SEARCH_URL = "https://html.duckduckgo.com/html/"

    def __init__(self, config: ResearchConfig):

        self.config = config
        self.llm = LLMEngine()

        self.search_semaphore = asyncio.Semaphore(config.search_concurrency)
        self.fetch_semaphore = asyncio.Semaphore(config.fetch_concurrency)

    async def run(self):

        start_time = time.perf_counter()

        console.rule("Cupid Research Agent")

        queries = await self.llm.generate_queries(self.config.topic)
        queries = queries[: self.config.max_queries]

        console.print("\nGenerated Queries")
        for q in queries:
            console.print(" •", q)

        async with httpx.AsyncClient(
            headers=self.config.headers,
            timeout=self.config.timeout,
            limits=self.config.limits,
        ) as client:

            with Progress() as progress:

                task = progress.add_task("Searching web", total=len(queries))

                results = []

                for q in queries:

                    r = await self.search(client, q)
                    results.extend(r)

                    progress.update(task, advance=1)

            results = sorted(results, key=lambda x: x.score, reverse=True)

            top_results = results[: self.config.pages_to_fetch]

            table = Table(title="Top Sources")

            table.add_column("#")
            table.add_column("Title")
            table.add_column("Domain")
            table.add_column("Score")

            for i, r in enumerate(top_results):
                table.add_row(str(i + 1), r.title[:60], r.domain, f"{r.score:.2f}")

            console.print(table)

            console.print("\nFetching pages")

            pages = await asyncio.gather(*[self.fetch_page(client, r.url) for r in top_results])

        corpus = [text for _, text in pages if text]

        chunks = self.chunk_corpus(corpus)

        console.print(f"\nProcessing {len(chunks)} text chunks")

        summaries = []

        for chunk in chunks:

            s = await self.llm.summarize_chunk(self.config.topic, chunk)
            summaries.append(s)

        final_summary = await self.llm.synthesize(self.config.topic, summaries)

        console.print(Panel(final_summary, title="Final Research Summary"))

        end_time = time.perf_counter()

        console.print(f"Total runtime: {end_time - start_time:.2f}s")

    async def search(self, client: httpx.AsyncClient, query: str):

        async with self.search_semaphore:

            r = await client.get(self.SEARCH_URL, params={"q": query})

            soup = BeautifulSoup(r.text, "html.parser")

            results = []

            for item in soup.select("div.result")[: self.config.results_per_query]:

                a = item.select_one("a.result__a")

                if not a:
                    continue

                title = a.text.strip()
                url = self.normalize_url(a.get("href"))

                snippet_el = item.select_one("a.result__snippet")
                snippet = snippet_el.text.strip() if snippet_el else ""

                domain = urlparse(url).netloc

                score = self.score(query, title + snippet)

                results.append(SearchResult(title, url, snippet, domain, score))

            return results

    async def fetch_page(self, client: httpx.AsyncClient, url: str):

        async with self.fetch_semaphore:

            try:

                r = await client.get(url)
                html = r.text

                if trafilatura:
                    text = trafilatura.extract(html)
                else:
                    soup = BeautifulSoup(html, "html.parser")
                    text = " ".join(p.text for p in soup.select("p"))

                if not text:
                    return url, ""

                text = re.sub(r"\s+", " ", text)

                return url, text

            except Exception:
                return url, ""

    def chunk_corpus(self, corpus: List[str]):

        joined = " ".join(corpus)

        size = self.config.chunk_size

        return [joined[i : i + size] for i in range(0, len(joined), size)]

    def score(self, query, text):

        terms = query.lower().split()
        text = text.lower()

        score = sum(text.count(t) for t in terms)

        return float(score)

    def normalize_url(self, href):

        if "uddg=" in href:

            parsed = parse_qs(urlparse(href).query)

            return unquote(parsed.get("uddg", [href])[0])

        return href


async def main(topic):

    config = ResearchConfig(topic=topic)

    agent = ResearchAgent(config)

    await agent.run()


if __name__ == "__main__":

    topic = " ".join(sys.argv[1:])

    if not topic:
        topic = input("Enter a research topic: ")

    asyncio.run(main(topic))
