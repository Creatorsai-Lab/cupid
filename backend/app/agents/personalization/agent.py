"""
Personalization Agent — LangGraph node for query generation.

Reads the user's prompt and stored profile fields, then asks Gemini to
produce 5 targeted, diverse search queries. These queries are written into
MemoryState as ``personalization_queries`` and consumed downstream by the
Research Agent.

Swarm contract:
- Input:  MemoryState with ``user_prompt`` + ``personalization``
- Output: dict updating ``personalization_queries``, ``current_agent``,
          ``agents_completed``

Dependency::

    pip install langchain-google-genai
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import StateGraph, END

from app.agents.state import MemoryState
from app.config import settings

logger = logging.getLogger(__name__)

# ── Prompt templates ──────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a search query strategist for social media content creators.

Your job: given a topic and a creator's profile, generate exactly 5 focused,
diverse web search queries that will surface the most relevant, authoritative,
and up-to-date information for creating authentic content.

Rules:
- Output exactly 5 queries, one per line
- Each query should be 3–9 words
- Cover different angles: data/statistics, expert opinion, recent trends,
  how-to/practical, and real-world examples
- Tailor every query to the creator's niche, audience, and goal
- No numbering, no bullet points, no explanations — only the queries
"""


def _build_user_message(prompt: str, persona: dict[str, Any]) -> str:
    """Format the creator profile + topic into a single user turn."""
    niche = (persona.get("content_niche") or "general").strip()
    goal = (persona.get("content_goal") or "educate and inform").strip()
    audience = (persona.get("target_audience") or "general audience").strip()
    country = (persona.get("target_country") or "").strip()
    intent = (persona.get("content_intent") or "").strip()
    usp = (persona.get("usp") or "").strip()
    bio = (persona.get("bio") or "").strip()

    lines = [
        f"- Niche: {niche}",
        f"- Content Goal: {goal}",
        f"- Target Audience: {audience}",
    ]
    if country:
        lines.append(f"- Target Country: {country}")
    if intent:
        lines.append(f"- Content Intent: {intent}")
    if usp:
        lines.append(f"- Creator USP: {usp}")
    if bio:
        lines.append(f"- Bio: {bio}")

    profile_block = "\n".join(lines)

    return (
        f"Creator Profile:\n{profile_block}\n\n"
        f"Topic: {prompt}\n\n"
        f"Generate 5 search queries:"
    )


# ── LangGraph node ────────────────────────────────────────────

async def personalization_node(state: MemoryState) -> dict[str, Any]:
    """
    LangGraph node: use Gemini to produce 5 personalized search queries.

    Reads ``user_prompt`` and ``personalization`` from state.
    Writes ``personalization_queries`` to the returned state delta.
    """
    user_prompt = (state.get("user_prompt") or "").strip()
    personalization = state.get("personalization") or {}

    logger.info("[personalization] starting — prompt=%r", user_prompt[:80])

    if not user_prompt:
        logger.warning("[personalization] empty prompt — skipping query generation")
        return {
            "personalization_queries": [],
            "current_agent": "personalization",
            "agents_completed": [*state.get("agents_completed", []), "personalization"],
        }

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import SystemMessage, HumanMessage
    except ImportError as exc:
        raise RuntimeError(
            "Personalization agent requires `langchain-google-genai`.\n"
            "Install it with:  pip install langchain-google-genai"
        ) from exc

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing from backend/.env. "
            "Add it as:  GEMINI_API_KEY=your-key-here"
        )

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0.4,
        max_output_tokens=256,
    )

    user_message = _build_user_message(user_prompt, personalization)

    response = await llm.ainvoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ])

    # Parse: one query per non-empty line, cap at 5
    raw: str = response.content.strip()
    queries: list[str] = [
        line.strip()
        for line in raw.splitlines()
        if line.strip()
    ][:5]

    logger.info("[personalization] generated %d queries: %s", len(queries), queries)

    return {
        "personalization_queries": queries,
        "current_agent": "personalization",
        "agents_completed": [*state.get("agents_completed", []), "personalization"],
    }


# ── Subgraph builder ──────────────────────────────────────────

def build_personalization_graph() -> StateGraph:
    """
    Build the personalization agent as a standalone LangGraph subgraph.

    Returns an uncompiled StateGraph — call ``.compile()`` before adding
    it as a node in the parent swarm orchestrator.
    """
    builder = StateGraph(MemoryState)
    builder.add_node("run", personalization_node)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder
