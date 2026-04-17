"""
Research Agent — LangGraph subgraph for autonomous web research.

Swarm orchestration compatible:
- Self-contained subgraph (single entry, single exit)
- Returns state delta — parent orchestrator handles routing

Pipeline:
    personalization_queries  (from MemoryState, set by Personalization Agent)
        → SearchPipeline.run()  (parallel search + extract)
        → assemble ResearchData
        → return state update

LangSmith: all nodes auto-traced; pipeline internals traced via @traceable.

Note: Query generation has been moved to the Personalization Agent.
The Research Agent reads ``personalization_queries`` from state and runs
the search pipeline against those queries.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar, cast

from langgraph.graph import StateGraph, END

from app.agents.state import MemoryState, ResearchData
from app.agents.research.search import SearchPipeline

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
    Execute the research pipeline. This is the LangGraph node function.

    Reads ``personalization_queries`` from state (produced by the
    Personalization Agent), runs the search + extraction pipeline, and
    returns a state delta with ``research_data``.

    Swarm contract:
    - Input:  MemoryState with ``personalization_queries``
    - Output: dict updating ``research_data``, ``current_agent``,
              ``agents_completed``
    """
    queries: list[str] = state.get("personalization_queries") or []
    user_prompt: str = (state.get("user_prompt") or "").strip()

    # Fallback: if personalization agent didn't run yet, use raw prompt
    if not queries and user_prompt:
        queries = [user_prompt]
        logger.warning(
            "[research] personalization_queries empty — falling back to raw prompt"
        )

    logger.info("[research] starting — queries=%s", queries)

    if not queries:
        return {
            "research_data": {
                "generated_keywords": [],
                "queries_used": [],
                "top_search_results": [],
                "fetched_pages": [],
                "research_summary": "No queries provided.",
            },
            "current_agent": "research",
            "agents_completed": [*state.get("agents_completed", []), "research"],
        }

    try:
        pipeline = SearchPipeline()
        results = await pipeline.run(queries)
        logger.info("[research] extracted %d quality pages", len(results))

        domains = list({r.domain for r in results})

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
                    "score": float(len(results) - i),
                }
                for i, r in enumerate(results)
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
                f"Searched {len(queries)} queries, extracted {len(results)} "
                f"pages across {', '.join(domains[:4])}."
            ),
        }

        return {
            "research_data": research_data,
            "current_agent": "research",
            "agents_completed": [
                *state.get("agents_completed", []),
                "research",
            ],
        }

    except Exception as exc:
        logger.error("[research] failed: %s", exc, exc_info=True)
        return {
            "error": f"Research agent failed: {exc}",
            "current_agent": "research",
            "status": "failed",
        }


# ── Subgraph builder ──────────────────────────────────────────

def build_research_graph() -> StateGraph:
    """
    Build the research agent as a LangGraph subgraph.

    Returns an uncompiled StateGraph — call ``.compile()`` before
    adding it as a node in the parent orchestrator.
    """
    builder = StateGraph(MemoryState)
    builder.add_node("run", research_node)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder
