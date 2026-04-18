"""
Personalization Agent — query decomposition for content research.

Decomposes a creator's topic into 5 orthogonal search queries covering
distinct retrieval angles. Uses a prioritized provider chain with
automatic fallback on rate-limit, auth, or transient errors.

Provider order (first available wins):
    1. Groq (Llama 3.1 8B)        — primary, very fast, generous free tier
    2. Hugging Face Inference API — fallback, free tier
    3. Local heuristic             — last resort, zero-LLM, never fails

Dependencies::

    pip install langchain-groq httpx
"""
from __future__ import annotations

import json
import logging
from typing import Any, Protocol

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.agents.state import MemoryState
from app.agents.personalization.local_heuristic import generate_queries as heuristic_queries
from app.config import settings

logger = logging.getLogger(__name__)

# ─── Prompt ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a research query strategist for social media creators. You decompose a topic \
into exactly 5 search queries, each targeting a distinct retrieval angle so together \
they surface comprehensive, non-overlapping information and all info should be latest year 2026.

THE 5 ANGLES (in order, one query per angle):
  1. FACTS      — statistics, data points, definitions, benchmarks
  2. RECENCY    — latest developments, current-year updates
  3. EXPERTISE  — what domain experts, researchers, or authoritative sources say
  4. PRACTICAL  — how-to, tutorials, implementation, real workflows
  5. CONTRARIAN — criticism, failures, edge cases, what doesn't work

QUERY RULES:
- 4 to 9 words each. Concrete nouns over adjectives.
- Anchor on specific entities, tools, numbers, or proper nouns when present.
- Tailor vocabulary to the creator's niche and audience sophistication.
- Queries must NOT overlap — each must surface different results.
- No question marks. No quotes. No site: operators. No numbering.

OUTPUT FORMAT (STRICT):
Return ONLY a JSON array of 5 strings. No prose, no markdown, no code fences.
Example: ["query one","query two","query three","query four","query five"]\
"""


def _build_context(prompt: str, persona: dict[str, Any]) -> str:
    fields = [
        ("Niche",    persona.get("content_niche")),
        ("Goal",     persona.get("content_goal")),
        ("Audience", persona.get("target_audience")),
        ("Region",   persona.get("target_country")),
        ("Intent",   persona.get("content_intent")),
        ("USP",      persona.get("usp")),
    ]
    ctx = "\n".join(f"- {k}: {v}" for k, v in fields if v and str(v).strip())
    return f"CREATOR CONTEXT\n{ctx}\n\nTOPIC\n{prompt}"


# ─── Provider interface ──────────────────────────────────────────

class QueryProvider(Protocol):
    name: str
    async def generate(self, system: str, user: str,
                       prompt: str, persona: dict[str, Any]) -> list[str]: ...


class GroqProvider:
    """Primary: Groq-hosted Llama 3.1 8B — very fast, generous free tier."""
    name = "groq-llama-3.1-8b"

    def __init__(self, api_key: str) -> None:
        from langchain_groq import ChatGroq
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",
            groq_api_key=api_key,
            temperature=0.4,
            max_tokens=256,
            timeout=10,
        )

    async def generate(self, system: str, user: str,
                       prompt: str, persona: dict[str, Any]) -> list[str]:
        response = await self.llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=user),
        ])
        return _parse_queries(response.content)


class HuggingFaceProvider:
    """
    Fallback: Hugging Face Inference API.

    Uses a chat-capable model via the router. Free tier is limited but
    adequate for occasional fallback usage.
    """
    name = "huggingface-llama-3.2"

    def __init__(self, api_key: str, model: str = "meta-llama/Llama-3.2-3B-Instruct") -> None:
        self.api_key = api_key
        self.model = model
        self.url = f"https://api-inference.huggingface.co/models/{model}"

    async def generate(self, system: str, user: str,
                       prompt: str, persona: dict[str, Any]) -> list[str]:
        # HF Inference API expects a single text input for most models
        combined = f"<|system|>\n{system}\n<|user|>\n{user}\n<|assistant|>\n"
        payload = {
            "inputs": combined,
            "parameters": {
                "max_new_tokens": 256,
                "temperature": 0.4,
                "return_full_text": False,
            },
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self.url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # HF returns a list of {"generated_text": "..."} objects
        if isinstance(data, list) and data:
            text = data[0].get("generated_text", "")
        elif isinstance(data, dict):
            text = data.get("generated_text", "") or data.get("error", "")
            if "error" in data:
                raise RuntimeError(f"HF API error: {data['error']}")
        else:
            text = ""

        return _parse_queries(text)


class HeuristicProvider:
    """
    Last resort: zero-LLM deterministic generator.
    Never raises, never returns empty.
    """
    name = "heuristic-local"

    async def generate(self, system: str, user: str,
                       prompt: str, persona: dict[str, Any]) -> list[str]:
        return heuristic_queries(prompt, persona)


# ─── Parsing ─────────────────────────────────────────────────────

def _parse_queries(raw: str) -> list[str]:
    """Extract up to 5 clean queries from provider output."""
    text = raw.strip()

    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].removeprefix("json").strip()

    # Try JSON first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            queries = [str(q).strip() for q in parsed if str(q).strip()]
            if queries:
                return _dedupe(queries)[:5]
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: one query per line
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
    """Assemble providers in priority order. Log which ones are available."""
    chain: list[QueryProvider] = []

    # ── Groq ──
    groq_key = getattr(settings, "groq_api_key", "")
    if groq_key:
        try:
            chain.append(GroqProvider(groq_key))
            logger.info("[personalization] Groq provider: ENABLED")
        except ImportError:
            logger.warning(
                "[personalization] Groq provider: DISABLED — "
                "`langchain-groq` not installed. Run: pip install langchain-groq"
            )
    else:
        logger.info("[personalization] Groq provider: DISABLED — GROQ_API_KEY missing in .env")

    # ── Hugging Face ──
    hf_key = getattr(settings, "huggingface_api_key", "")
    if hf_key:
        try:
            chain.append(HuggingFaceProvider(hf_key))
            logger.info("[personalization] Hugging Face provider: ENABLED")
        except Exception as exc:
            logger.warning(
                "[personalization] Hugging Face provider: DISABLED — init failed: %s",
                exc,
            )
    else:
        logger.info("[personalization] Hugging Face provider: DISABLED — HUGGINGFACE_API_KEY missing in .env")

    # ── Heuristic (always available) ──
    chain.append(HeuristicProvider())
    logger.info("[personalization] Local heuristic provider: ENABLED (always-on fallback)")

    active = ", ".join(p.name for p in chain)
    logger.info("[personalization] active chain: %s", active)
    return chain


def _classify_error(exc: Exception) -> str:
    err = str(exc).lower()
    if "429" in err or "rate" in err or "quota" in err or "resource_exhausted" in err:
        return "rate-limited"
    if "401" in err or "403" in err or "unauthorized" in err or "api key" in err:
        return "auth-failure"
    if "timeout" in err or "timed out" in err:
        return "timeout"
    return "error"


async def _run_chain(
    system: str,
    user: str,
    prompt: str,
    persona: dict[str, Any],
) -> tuple[list[str], str]:
    """Try each provider until one succeeds. Returns (queries, provider_name)."""
    chain = _build_provider_chain()

    for provider in chain:
        try:
            queries = await provider.generate(system, user, prompt, persona)
            if len(queries) >= 3:
                if not isinstance(provider, (GroqProvider,)):
                    logger.warning(
                        "[personalization] using fallback provider: %s",
                        provider.name,
                    )
                return queries, provider.name

            logger.warning(
                "[personalization] %s returned only %d queries — falling through",
                provider.name, len(queries),
            )

        except Exception as exc:
            kind = _classify_error(exc)
            logger.warning(
                "[personalization] %s failed (%s): %s",
                provider.name, kind, str(exc)[:200],
            )
            continue

    # Should never reach — HeuristicProvider never raises
    logger.error("[personalization] entire provider chain failed — impossible state")
    return [], "none"


# ─── LangGraph node ──────────────────────────────────────────────

async def personalization_node(state: MemoryState) -> dict[str, Any]:
    """
    Generate 5 angle-decomposed queries for the Research Agent.

    Reads:  user_prompt, personalization
    Writes: personalization_queries, current_agent, agents_completed
    """
    prompt    = (state.get("user_prompt") or "").strip()
    persona   = state.get("personalization") or {}
    completed = state.get("agents_completed", [])

    if not prompt:
        logger.warning("[personalization] empty prompt — skipping")
        return {
            "personalization_queries": [],
            "current_agent": "personalization",
            "agents_completed": [*completed, "personalization"],
        }

    logger.info("[personalization] start — topic=%r", prompt[:60])

    user_msg = _build_context(prompt, persona)
    queries, provider_used = await _run_chain(SYSTEM_PROMPT, user_msg, prompt, persona)

    logger.info(
        "[personalization] done — provider=%s queries=%d",
        provider_used, len(queries),
    )

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