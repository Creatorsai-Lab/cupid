"""
Personalization Agent — query decomposition for content research.

Decomposes a creator's topic into 5 orthogonal search queries covering
distinct retrieval angles. Uses a prioritized LLM chain with automatic
fallback to a sophisticated local heuristic on failure.

Provider order:
    1. Gemini 2.0 Flash   (primary — fast, free tier)
    2. Groq (Llama 3.1)   (fallback — free, very fast)
    3. Local heuristic    (last resort — zero LLM, deterministic)

Dependencies::

    pip install langchain-google-genai langchain-groq
"""
from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from langgraph.graph import END, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import MemoryState
from app.config import settings
from app.agents.personalization.local_heuristic import generate_queries as heuristic_queries

logger = logging.getLogger(__name__)

# ─── Prompt ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a research query strategist for social media creators. You decompose a topic \
into exactly 5 search queries, each targeting a distinct retrieval angle so together \
they surface comprehensive, non-overlapping information.

THE 5 ANGLES (in order, one query per angle):
  1. FACTS      — statistics, data points, definitions, benchmarks
  2. RECENCY    — latest developments, 2025 updates, "this week/month"
  3. EXPERTISE  — what domain experts, researchers, or authoritative sources say
  4. PRACTICAL  — how-to, tutorials, implementation, real workflows
  5. CONTRARIAN — criticism, failures, edge cases, what doesn't work

QUERY RULES:
- 4 to 9 words each. Concrete nouns over adjectives.
- Anchor on specific entities, tools, numbers, or proper nouns when possible.
- Tailor vocabulary to the creator's niche and audience sophistication.
- Queries must NOT overlap — each must surface different results than the others.
- No question marks. No quotes. No site: operators. No numbering.

OUTPUT FORMAT (STRICT):
Return ONLY a JSON array of 5 strings. No prose, no markdown, no code fences.
Example: ["query one","query two","query three","query four","query five"]\
"""


def _build_context(prompt: str, persona: dict[str, Any]) -> str:
    """Compact creator context — one line per signal, skip empty fields."""
    fields = [
        ("Niche",     persona.get("content_niche")),
        ("Goal",      persona.get("content_goal")),
        ("Audience",  persona.get("target_audience")),
        ("Region",    persona.get("target_country")),
        ("Intent",    persona.get("content_intent")),
        ("USP",       persona.get("usp")),
    ]
    context = "\n".join(f"- {k}: {v}" for k, v in fields if v and str(v).strip())
    return f"CREATOR CONTEXT\n{context}\n\nTOPIC\n{prompt}"


# ─── Provider interface ──────────────────────────────────────────

class QueryProvider(Protocol):
    name: str
    async def generate(self, system: str, user: str,
                       prompt: str, persona: dict[str, Any]) -> list[str]: ...


class GeminiProvider:
    """Primary: Gemini 2.0 Flash via Google AI."""
    name = "gemini-2.0-flash"

    def __init__(self, api_key: str) -> None:
        from langchain_google_genai import ChatGoogleGenerativeAI
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=api_key,
            temperature=0.4,
            max_output_tokens=256,
        )

    async def generate(self, system: str, user: str,
                       prompt: str, persona: dict[str, Any]) -> list[str]:
        response = await self.llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=user),
        ])
        return _parse_queries(response.content)


class GroqProvider:
    """Fallback: Groq (Llama 3.1) — generous free tier, very fast inference."""
    name = "groq-llama-3.1-8b"

    def __init__(self, api_key: str) -> None:
        from langchain_groq import ChatGroq
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",
            groq_api_key=api_key,
            temperature=0.4,
            max_tokens=256,
        )

    async def generate(self, system: str, user: str,
                       prompt: str, persona: dict[str, Any]) -> list[str]:
        response = await self.llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=user),
        ])
        return _parse_queries(response.content)


class HeuristicProvider:
    """
    Last resort: zero-LLM deterministic generator.
    Delegates to the local_heuristic module which implements
    persona-aware angle decomposition using structured NLP.
    """
    name = "heuristic-local"

    async def generate(self, system: str, user: str,
                       prompt: str, persona: dict[str, Any]) -> list[str]:
        # Heuristic is sync and pure — no await needed
        return heuristic_queries(prompt, persona)


# ─── Parsing ─────────────────────────────────────────────────────

def _parse_queries(raw: str) -> list[str]:
    """Extract exactly 5 clean queries from LLM output."""
    text = raw.strip()

    if text.startswith("```"):
        text = text.split("```")[1]
        text = text.removeprefix("json").strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            queries = [str(q).strip() for q in parsed if str(q).strip()]
            if queries:
                return _dedupe(queries)[:5]
    except (json.JSONDecodeError, ValueError):
        pass

    lines = [
        line.lstrip("-*•0123456789. ").strip().strip('"').strip("'")
        for line in text.splitlines()
    ]
    queries = [line for line in lines if line and len(line.split()) >= 3]
    return _dedupe(queries)[:5]


def _dedupe(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        key = " ".join(q.lower().split())
        if key not in seen:
            seen.add(key)
            out.append(q)
    return out


# ─── Provider chain ──────────────────────────────────────────────

def _build_provider_chain() -> list[QueryProvider]:
    """Assemble available providers in priority order."""
    chain: list[QueryProvider] = []

    if getattr(settings, "gemini_api_key", None):
        try:
            chain.append(GeminiProvider(settings.gemini_api_key))
        except ImportError:
            logger.warning("[personalization] langchain-google-genai not installed, skipping Gemini")

    if getattr(settings, "groq_api_key", None):
        try:
            chain.append(GroqProvider(settings.groq_api_key))
        except ImportError:
            logger.warning("[personalization] langchain-groq not installed, skipping Groq")

    chain.append(HeuristicProvider())  # always available
    return chain


async def _run_chain(
    system: str,
    user: str,
    prompt: str,
    persona: dict[str, Any],
) -> tuple[list[str], str]:
    """Try each provider until one succeeds. Returns (queries, provider_name)."""
    for provider in _build_provider_chain():
        try:
            queries = await provider.generate(system, user, prompt, persona)
            if len(queries) >= 3:
                if provider.name != "gemini-2.0-flash":
                    logger.warning("[personalization] using fallback: %s", provider.name)
                return queries, provider.name
            logger.warning("[personalization] %s returned only %d queries",
                           provider.name, len(queries))
        except Exception as exc:
            err_str = str(exc)
            is_rate_limit = (
                "429" in err_str
                or "RESOURCE_EXHAUSTED" in err_str
                or "rate" in err_str.lower()
            )
            logger.warning("[personalization] %s failed (%s): %s",
                           provider.name,
                           "rate-limited" if is_rate_limit else "error",
                           err_str[:200])
            continue

    # Guarantee: HeuristicProvider never raises and never returns empty
    logger.error("[personalization] all providers exhausted — this should not happen")
    return [], "none"


# ─── LangGraph node ──────────────────────────────────────────────

async def personalization_node(state: MemoryState) -> dict[str, Any]:
    """
    Generate 5 angle-decomposed search queries for the Research Agent.

    Reads:  user_prompt, personalization
    Writes: personalization_queries, current_agent, agents_completed
    """
    prompt  = (state.get("user_prompt") or "").strip()
    persona = state.get("personalization") or {}
    completed = state.get("agents_completed", [])

    if not prompt:
        logger.warning("[personalization] empty prompt, skipping")
        return {
            "personalization_queries": [],
            "current_agent": "personalization",
            "agents_completed": [*completed, "personalization"],
        }

    logger.info("[personalization] start — topic=%r", prompt[:60])

    user_msg = _build_context(prompt, persona)
    queries, provider_used = await _run_chain(SYSTEM_PROMPT, user_msg, prompt, persona)

    logger.info("[personalization] done — provider=%s queries=%d",
                provider_used, len(queries))

    return {
        "personalization_queries": queries,
        "current_agent": "personalization",
        "agents_completed": [*completed, "personalization"],
    }


# ─── Subgraph builder ────────────────────────────────────────────

def build_personalization_graph() -> StateGraph:
    """Standalone subgraph. Call .compile() before mounting on the swarm."""
    builder = StateGraph(MemoryState)
    builder.add_node("run", personalization_node)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder