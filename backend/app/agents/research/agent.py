"""
Research Agent — LangGraph subgraph for autonomous web research.

Swarm orchestration compatible:
- Self-contained subgraph (single entry, single exit)
- Returns state delta — parent orchestrator handles routing
- Uses Command for explicit next-agent handoff when needed

Pipeline:
    user_prompt + personalization
        → generate_queries()  (lightweight, no LLM)
        → SearchPipeline.run()  (parallel search + extract)
        → assemble ResearchData
        → return state update

LangSmith: all nodes auto-traced; pipeline internals traced via @traceable.

Usage as a swarm node::

    from app.agents.research import build_research_graph

    research = build_research_graph().compile()

    # In the parent swarm orchestrator:
    swarm = StateGraph(MemoryState)
    swarm.add_node("research", research)
    swarm.add_node("composer", composer)
    swarm.add_conditional_edges("router", route_fn, {...})
"""
from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar, cast

from langgraph.graph import StateGraph, END
from langgraph.types import Command

from app.agents.state import MemoryState, ResearchData
from app.agents.research.search import SearchPipeline
from app.config import settings

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

from app.config import settings

def build_headers() -> dict[str, str]:
    if not settings.gemini_api_key:
        raise RuntimeError("GOOGLE_API_KEY missing in backend/.env")
    return {"Authorization": f"Bearer {settings.gemini_api_key}"}


# ── Query generation ──────────────────────────────────────────

def generate_queries(
    prompt: str,
    context: dict[str, Any] | None = None,
    max_queries: int = 4,
) -> list[str]:
    """
    Derive search queries from the user prompt and profile context.

    Intentionally lightweight — DDG already handles relevance ranking.
    We just need breadth: the original prompt, a domain-qualified
    variant, a recency variant, and a shortened broad variant.

    For LLM-powered query decomposition (Perplexity Pro Search style),
    swap this function with ``generate_queries_with_llm`` below.
    """
    prompt = prompt.strip()
    if not prompt:
        return []

    queries: list[str] = [prompt]
    ctx = context or {}

    # Domain-qualified variant
    niche = (ctx.get("content_niche") or "").strip()
    if niche and niche.lower() not in prompt.lower():
        queries.append(f"{prompt} {niche}")

    # Recency variant
    queries.append(f"{prompt} latest")

    # Broad variant for long prompts — first few content words
    words = prompt.split()
    if len(words) > 6:
        queries.append(" ".join(words[:5]))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        key = q.strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)

    return unique[:max_queries]


async def generate_queries_with_llm(
    prompt: str,
    context: dict[str, Any] | None = None,
    max_queries: int = 4,
    model: str = "claude-sonnet-4-20250514",
) -> list[str]:
    """
    LLM-powered query decomposition (optional upgrade path).

    Decomposes complex prompts into targeted sub-queries the way
    Perplexity Pro Search does. Requires ``langchain-anthropic``.

    Usage::

        # In research_node, replace:
        queries = generate_queries(prompt, ctx)
        # with:
        queries = await generate_queries_with_llm(prompt, ctx)
    """
    try:
        from langchain_anthropic import ChatAnthropic  # type: ignore[reportMissingImports]
        from langchain_core.messages import SystemMessage, HumanMessage  # type: ignore[reportMissingImports]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "LLM query decomposition requires optional dependencies. "
            "Install `langchain-anthropic` and `langchain-core`."
        ) from exc

    llm = ChatAnthropic(model=model, temperature=0, max_tokens=256)

    ctx = context or {}
    niche = (ctx.get("content_niche") or "").strip()
    niche_hint = f" The user's content niche is: {niche}." if niche else ""

    response = await llm.ainvoke([
        SystemMessage(content=(
            "You are a search query generator. Given a research topic, "
            "produce 2-4 short, diverse web search queries (one per line). "
            "Each query should be 3-8 words. No numbering, no explanation."
            f"{niche_hint}"
        )),
        HumanMessage(content=prompt),
    ])

    lines = [
        line.strip()
        for line in response.content.strip().splitlines()
        if line.strip()
    ]
    return lines[:max_queries]


# ── LangGraph node ────────────────────────────────────────────

@traceable(name="research_agent")
async def research_node(state: MemoryState) -> dict[str, Any]:
    """
    Execute the research pipeline. This is the LangGraph node function.

    Reads ``user_prompt`` and ``personalization`` from state, runs the
    search pipeline, and returns a state delta with ``research_data``.

    Swarm contract:
    - Input:  MemoryState with at least ``user_prompt``
    - Output: dict updating ``research_data``, ``current_agent``,
              ``agents_completed``
    - Routing: parent graph's conditional edges decide the next agent
    """
    user_prompt = state.get("user_prompt", "")
    personalization = cast(dict[str, Any], state.get("personalization", {}))

    logger.info("[research] starting — prompt=%s", user_prompt[:80])

    try:
        # 1 — Generate search queries
        queries = generate_queries(user_prompt, personalization)
        logger.info("[research] queries=%s", queries)

        # 2 — Run search + extract pipeline
        pipeline = SearchPipeline()
        results = await pipeline.run(queries)
        logger.info("[research] extracted %d quality pages", len(results))

        # 3 — Assemble state-compatible ResearchData
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


# ── Swarm-compatible subgraph builder ─────────────────────────

def build_research_graph() -> StateGraph:
    """
    Build the research agent as a LangGraph subgraph.

    Returns an uncompiled StateGraph — call ``.compile()`` before
    adding it as a node in the parent orchestrator.

    Swarm integration example::

        from app.agents.research import build_research_graph
        from app.agents.composer import build_composer_graph

        # Build agent subgraphs
        research = build_research_graph().compile()
        composer  = build_composer_graph().compile()

        # Swarm orchestrator
        def route_next(state: MemoryState) -> str:
            if "research" not in state.get("agents_completed", []):
                return "research"
            if "composer" not in state.get("agents_completed", []):
                return "composer"
            return "__end__"

        orchestrator = StateGraph(MemoryState)
        orchestrator.add_node("research", research)
        orchestrator.add_node("composer", composer)
        orchestrator.set_conditional_entry_point(route_next)
        orchestrator.add_conditional_edges("research", route_next)
        orchestrator.add_conditional_edges("composer", route_next)

        app = orchestrator.compile()
    """
    builder = StateGraph(MemoryState)
    builder.add_node("run", research_node)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder