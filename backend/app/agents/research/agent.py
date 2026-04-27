"""
Research Agent — LangGraph subgraph for autonomous web research.

Pipeline:
    personalization_queries (from MemoryState, set by Personalization Agent)
        → SearchPipeline.run()  (parallel search + extract)
        → assemble ResearchData
        → return state update

LangSmith: all nodes auto-traced; pipeline internals traced via @traceable.

Note: Query generation lives in the Personalization Agent.
The Research Agent reads ``personalization_queries`` from state.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, TypeVar, cast

from langgraph.graph import END, StateGraph

from app.agents.research.search import SearchPipeline
from app.agents.state import MemoryState, ResearchData
from app.core.logging_config import get_agent_logger

try:
    from langsmith import traceable as _traceable
    traceable = cast(Any, _traceable)
except ImportError:
    F = TypeVar("F", bound=Callable[..., Any])

    def traceable(*args: Any, **kwargs: Any):  # type: ignore[misc]
        def decorator(fn: F) -> F:
            return fn
        return decorator

logger = get_agent_logger("research")


# ── LangGraph node ────────────────────────────────────────────

@traceable(name="research_agent")
async def research_node(state: MemoryState) -> dict[str, Any]:
    """
    Execute the research pipeline.

    Reads:  personalization_queries, user_prompt
    Writes: research_data, current_agent, agents_completed
    """
    run_id = state.get("run_id", "unknown")
    queries: list[str] = state.get("personalization_queries") or []
    user_prompt: str = (state.get("user_prompt") or "").strip()
    persona = state.get("personalization") or {}
    completed = state.get("agents_completed", [])

    # Log agent start
    logger.agent_start(
        run_id,
        queries_count=len(queries),
        user_prompt=user_prompt[:100] + "..." if len(user_prompt) > 100 else user_prompt,
        niche=persona.get("content_niche", "-"),
        region=persona.get("target_country", "-"),
    )

    # Fallback if personalization agent didn't run
    if not queries and user_prompt:
        queries = [user_prompt]
        logger.warning("No personalization queries - using raw prompt as single query", run_id)

    if not queries:
        logger.warning("No queries and no prompt - skipping research", run_id)
        logger.agent_complete(run_id, status="skipped", pages_fetched=0)
        return {
            "research_data": _empty_research_data(),
            "current_agent": "research",
            "agents_completed": [*completed, "research"],
        }

    # Log input queries
    logger.info("─" * 10, run_id)
    logger.info("📋 INPUT QUERIES:", run_id)
    for i, q in enumerate(queries, 1):
        logger.info(f"  [{i}] {q}", run_id)
    logger.info("─" * 10, run_id)

    # Run search pipeline
    logger.log_step(run_id, "Executing search pipeline")
    start_time = time.time()
    
    try:
        results = await SearchPipeline().run(queries, persona=persona)
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log results
        domains = sorted({r.domain for r in results})
        logger.log_metric(run_id, "pages_fetched", len(results))
        logger.log_metric(run_id, "unique_domains", len(domains))
        logger.log_metric(run_id, "latency_ms", latency_ms)
        
        # Log fetched pages
        logger.info("─" * 10, run_id)
        logger.info("📄 FETCHED PAGES:", run_id)
        for i, r in enumerate(results, 1):
            logger.info(
                f"  [{i:2d}] {r.domain:30s} | {r.text_length:6d} chars | {r.title[:50]}",
                run_id
            )
        logger.info("─" * 10, run_id)
        
        # Log domain distribution
        logger.info("🌐 DOMAIN DISTRIBUTION:", run_id)
        for domain in domains[:10]:  # Top 10 domains
            count = sum(1 for r in results if r.domain == domain)
            logger.info(f"  {domain:30s} : {count} pages", run_id)
        if len(domains) > 10:
            logger.info(f"  ... and {len(domains) - 10} more domains", run_id)
        
    except Exception as exc:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.agent_error(run_id, exc)
        return {
            "research_data": _empty_research_data(error=str(exc)),
            "current_agent": "research",
            "agents_completed": [*completed, "research"],
        }

    # Assemble research data
    research_data: ResearchData = {
        "generated_keywords": queries,
        "queries_used": queries,
        "top_search_results": [
            {
                "query": r.query,
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "domain": r.domain,
                "score": round(r.score, 3),
            }
            for r in results
        ],
        "fetched_pages": [
            {
                "url": r.url,
                "title": r.title,
                "domain": r.domain,
                "text_content": r.text_content,
                "text_length": r.text_length,
                "image_url": r.image_url,
            }
            for r in results
        ],
        "research_summary": (
            f"Searched {len(queries)} queries, extracted {len(results)} pages "
            f"across {len(domains)} domains ({', '.join(domains[:4])}"
            f"{'...' if len(domains) > 4 else ''})."
            if results else
            "Search returned no usable pages."
        ),
    }

    logger.agent_complete(
        run_id,
        pages_fetched=len(results),
        unique_domains=len(domains),
        latency_ms=f"{latency_ms}ms",
        avg_page_length=f"{sum(r.text_length for r in results) // max(len(results), 1)} chars",
    )

    return {
        "research_data": research_data,
        "current_agent": "research",
        "agents_completed": [*completed, "research"],
    }


def _empty_research_data(error: str | None = None) -> ResearchData:
    summary = f"Research failed: {error}" if error else "No queries provided."
    return {
        "generated_keywords": [],
        "queries_used": [],
        "top_search_results": [],
        "fetched_pages": [],
        "research_summary": summary,
    }


# ── Subgraph builder ──────────────────────────────────────────

def build_research_graph() -> StateGraph:
    """Standalone subgraph. Call .compile() before mounting on the swarm."""
    builder = StateGraph(MemoryState)
    builder.add_node("run", research_node)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder