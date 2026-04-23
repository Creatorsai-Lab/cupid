"""
Composer Agent — LangGraph subgraph that generates 3 platform-ready post variants.

Pipeline:
    1. SOURCE RANK    — BM25 + persona, pick top 3 of N fetched pages
    2. EVIDENCE       — 1 LLM call extracts atomic facts from top 3
    3. PARALLEL GEN   — 3 LLM calls (hook-first / data-driven / story-led)
    4. QUALITY SCORE  — deterministic multi-axis scoring + hashtag extraction
    5. EMIT           — return 3 scored variants to state

Provider chain (reuses personalization pattern):
    Groq (Llama 3.3 70B)  →  Hugging Face  →  bail out
    No local fallback here — if all LLMs fail we emit an error, because
    deterministic composition without an LLM would be a different product.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Callable, TypeVar, cast

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.agents.composer.evidence_distiller import distill_evidence
from app.agents.composer.platform_rules import rule_for
from app.agents.composer.prompts import ANGLE_PROMPTS, build_user_message
from app.agents.composer.quality_scorer import score_variant
from app.agents.composer.source_ranker import rank_sources
from app.agents.state import MemoryState
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

ANGLES = ("hook_first", "data_driven", "story_led")

# ─── LLM providers ──────────────────────────────────────────────

def _get_groq_llm() -> Any | None:
    """Groq: Llama 3.3 70B — quality + speed."""
    key = getattr(settings, "groq_api_key", "") or ""
    if not key:
        return None
    try:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.3-70b-versatile",
            groq_api_key=key,
            temperature=0.7,      # higher than personalization — creative writing
            max_tokens=1024,
            timeout=20,
        )
    except ImportError:
        logger.warning("[composer] langchain-groq not installed")
        return None


class _HFLLM:
    """Minimal HF wrapper matching the `.ainvoke([messages])` interface."""

    def __init__(self, api_key: str, model: str = "meta-llama/Llama-3.2-3B-Instruct"):
        self.api_key = api_key
        self.url = f"https://api-inference.huggingface.co/models/{model}"

    async def ainvoke(self, messages: list) -> Any:
        system = next((m.content for m in messages if isinstance(m, SystemMessage)), "")
        user = next((m.content for m in messages if isinstance(m, HumanMessage)), "")
        prompt = f"<|system|>\n{system}\n<|user|>\n{user}\n<|assistant|>\n"
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 800,
                "temperature": 0.7,
                "return_full_text": False,
            },
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self.url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text = ""
        if isinstance(data, list) and data:
            text = data[0].get("generated_text", "")
        elif isinstance(data, dict):
            if "error" in data:
                raise RuntimeError(f"HF API error: {data['error']}")
            text = data.get("generated_text", "")

        class _Response:
            def __init__(self, content: str):
                self.content = content
        return _Response(text)


def _get_hf_llm() -> Any | None:
    key = getattr(settings, "huggingface_api_key", "") or ""
    return _HFLLM(key) if key else None


async def _pick_llm() -> tuple[Any, str]:
    """Return (llm, name) of the first healthy provider."""
    groq = _get_groq_llm()
    if groq is not None:
        return groq, "groq-llama-3.3-70b"
    hf = _get_hf_llm()
    if hf is not None:
        return hf, "huggingface-llama-3.2"
    raise RuntimeError("No LLM providers configured for Composer")


# ─── Variant generation ─────────────────────────────────────────

async def _generate_variant(
    llm: Any,
    angle: str,
    user_message: str,
) -> str | None:
    """Run one angle prompt and return the post text, or None on failure."""
    system_prompt = ANGLE_PROMPTS[angle]
    try:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])
        text = _clean_output(response.content)
        return text if text else None
    except Exception as exc:
        logger.warning("[composer] angle=%s failed: %s", angle, str(exc)[:120])
        return None


def _clean_output(raw: str) -> str:
    """Strip common LLM junk: code fences, preambles, stray quotes."""
    text = raw.strip()

    # Remove code fences
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].lstrip()
            # Drop language tag line if present
            if "\n" in text and text.split("\n", 1)[0].lower() in ("markdown", "text", ""):
                text = text.split("\n", 1)[1]

    # Strip leading "Post:", "Output:", etc.
    text = re.sub(
        r"^(here['']?s the post[:\-]?|post[:\-]|output[:\-]|response[:\-])\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # Remove wrapping quotes
    if len(text) > 2 and text[0] in ('"', "'") and text[-1] == text[0]:
        text = text[1:-1].strip()

    return text


def _extract_hashtags(content: str) -> tuple[str, list[str]]:
    """Split hashtags out of content body so we can render them separately."""
    hashtags = re.findall(r"#\w+", content)
    body = re.sub(r"\s*#\w+", "", content).strip()
    return body, hashtags


# ─── LangGraph node ─────────────────────────────────────────────

@traceable(name="composer_agent")
async def composer_node(state: MemoryState) -> dict[str, Any]:
    """
    Generate 3 post variants from the research data + persona.

    Reads:  user_prompt, personalization, research_data, target_platform
    Writes: composer_output (list of 3 variants), current_agent, agents_completed
    """
    prompt        = (state.get("user_prompt") or "").strip()
    persona       = state.get("personalization") or {}
    research      = state.get("research_data") or {}
    platform      = state.get("target_platform") or "All"
    completed     = state.get("agents_completed", [])

    pages = research.get("fetched_pages", [])
    rule  = rule_for(platform)

    logger.info(
        "[composer] start — platform=%s pages=%d persona_niche=%s",
        rule.name, len(pages), persona.get("content_niche") or "-",
    )

    if not pages:
        logger.warning("[composer] no research pages — cannot compose")
        return {
            "composer_output": [],
            "current_agent": "composer",
            "agents_completed": [*completed, "composer"],
            "error": "No research data available for composition.",
        }

    # 1 — Rank and pick top 3 sources
    top_sources = rank_sources(pages, prompt, persona, top_k=3)

    # 2 — Distill facts (1 LLM call)
    try:
        llm, llm_name = await _pick_llm()
    except RuntimeError as exc:
        logger.error("[composer] no LLM available: %s", exc)
        return {
            "composer_output": [],
            "current_agent": "composer",
            "agents_completed": [*completed, "composer"],
            "error": str(exc),
        }

    logger.info("[composer] using LLM: %s", llm_name)
    facts = await distill_evidence(llm, prompt, top_sources)

    # 3 — Build the shared user message once
    user_message = build_user_message(prompt, facts, persona, rule)

    # 4 — Generate 3 variants in parallel
    gen_tasks = [_generate_variant(llm, angle, user_message) for angle in ANGLES]
    raw_variants = await asyncio.gather(*gen_tasks)

    # 5 — Score and package
    variants_out: list[dict[str, Any]] = []
    for angle, raw in zip(ANGLES, raw_variants, strict=True):
        if not raw:
            continue
        body, hashtags = _extract_hashtags(raw)
        # Enforce hashtag limit even if LLM ignored the instruction
        hashtags = hashtags[: rule.max_hashtags] if rule.use_hashtags else []
        final_content = body + ((" " + " ".join(hashtags)) if hashtags else "")

        score = score_variant(final_content, facts, persona, rule)

        variants_out.append({
            "angle": angle,
            "platform": rule.name,
            "content": final_content,
            "hashtags": hashtags,
            "char_count": len(final_content),
            "quality": {
                "composite": score.composite,
                "length_fit": score.length_fit,
                "grounding": score.grounding,
                "persona_match": score.persona_match,
                "hook_strength": score.hook_strength,
                "passes": score.passes_threshold,
            },
        })

    # Sort best to worst so frontend can render in order
    variants_out.sort(key=lambda v: v["quality"]["composite"], reverse=True)

    logger.info(
        "[composer] done — %d/%d variants produced (scores: %s)",
        len(variants_out), len(ANGLES),
        [v["quality"]["composite"] for v in variants_out],
    )

    return {
        "composer_output": variants_out,
        "composer_evidence": facts,
        "composer_sources": [
            {
                "title": s.get("title"),
                "url": s.get("url"),
                "domain": s.get("domain"),
                "rank_score": s.get("rank_score"),
            }
            for s in top_sources
        ],
        "current_agent": "composer",
        "agents_completed": [*completed, "composer"],
    }


# ─── Subgraph builder ───────────────────────────────────────────

def build_composer_graph() -> StateGraph:
    """Standalone subgraph. Call .compile() before mounting on the swarm."""
    builder = StateGraph(MemoryState)
    builder.add_node("run", composer_node)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder