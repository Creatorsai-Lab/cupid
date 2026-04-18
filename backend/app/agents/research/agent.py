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
from typing import Any, Callable, TypeVar, cast

from langgraph.graph import END, StateGraph

from app.agents.research.search import SearchPipeline
from app.agents.state import MemoryState, ResearchData

try:
    from langsmith import traceable as _traceable
    traceable = cast(Any, _traceable)
except ImportError:
    F = TypeVar("F", bound=Callable[..., Any])

    def traceable(*args: Any, **kwargs: Any):  # type: ignore[misc]
        def decorator(fn: F) -> F:
            return fn
        return decorator

logger = logging.getLogger(__name__)


# ── LangGraph node ────────────────────────────────────────────

@traceable(name="research_agent")
async def research_node(state: MemoryState) -> dict[str, Any]:
    """
    Execute the research pipeline.

    Reads:  personalization_queries, user_prompt
    Writes: research_data, current_agent, agents_completed
    """
    queries: list[str] = state.get("personalization_queries") or []
    user_prompt: str = (state.get("user_prompt") or "").strip()
    completed = state.get("agents_completed", [])

    # Fallback if personalization agent didn't run
    if not queries and user_prompt:
        queries = [user_prompt]
        logger.warning("[research] no personalization_queries — using raw prompt")

    if not queries:
        logger.warning("[research] no queries and no prompt — skipping")
        return {
            "research_data": _empty_research_data(),
            "current_agent": "research",
            "agents_completed": [*completed, "research"],
        }

    logger.info("[research] start — %d queries", len(queries))

    try:
        results = await SearchPipeline().run(queries)
    except Exception as exc:
        logger.error("[research] pipeline failed: %s", exc, exc_info=True)
        return {
            "research_data": _empty_research_data(error=str(exc)),
            "current_agent": "research",
            "agents_completed": [*completed, "research"],
        }

    domains = sorted({r.domain for r in results})
    logger.info(
        "[research] done — %d pages across %d domains",
        len(results), len(domains),
    )

    research_data: ResearchData = {
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

    return {
        "research_data": research_data,
        "current_agent": "research",
        "agents_completed": [*completed, "research"],
    }


def _empty_research_data(error: str | None = None) -> ResearchData:
    summary = f"Research failed: {error}" if error else "No queries provided."
    return {
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