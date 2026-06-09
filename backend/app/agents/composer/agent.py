"""
Composer Agent — Generates 3 highly personalized content drafts in parallel.

Utilizes a prioritized provider chain: Groq (Llama 3.3 70B) -> Hugging Face.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.agents.composer.compose import (
    build_composer_system_prompt,
    build_composer_user_prompt,
)
from app.agents.state import MemoryState
from app.config import settings
from app.core.logging_config import get_agent_logger

logger = get_agent_logger("composer")

# ─── Provider Factory ──────────────────────────────────────────


def _get_groq_llm() -> Any | None:
    """Primary Frontier Provider: Groq Llama 3.3 70B"""
    key = getattr(settings, "groq_api_key", "") or ""
    if not key:
        return None
    try:
        from langchain_groq import ChatGroq

        return ChatGroq(
            model="llama-3.3-70b-versatile",
            groq_api_key=key,
            temperature=0.7,  # Balanced temperature for stylistic variance across drafts
            max_tokens=2500,  # Highly expanded token runway for long articles
            timeout=25,
        )
    except Exception as exc:
        logger.warning(f"[composer] Groq initialization failed: {exc}")
        return None


class _HFLLM:
    """Fallback Provider Interface for HuggingFace Inference Routers"""

    def __init__(self, api_key: str, model: str = "meta-llama/Llama-3.2-3B-Instruct"):
        self.api_key = api_key
        self.url = f"https://api-inference.huggingface.co/models/{model}"

    async def ainvoke(self, messages: list) -> Any:
        system = next((m.content for m in messages if isinstance(m, SystemMessage)), "")
        user = next((m.content for m in messages if isinstance(m, HumanMessage)), "")
        prompt = f"<|system|>\n{system}\n<|user|>\n{user}\n<|assistant|>\n"

        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 1500,
                "temperature": 0.7,
                "return_full_text": False,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self.url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text = (
            data[0].get("generated_text", "") if isinstance(data, list) and data else ""
        )

        class _Response:
            def __init__(self, content: str):
                self.content = content

        return _Response(text)


async def _pick_llm() -> tuple[Any, str]:
    if groq := _get_groq_llm():
        return groq, "groq-llama-3.3-70b"
    hf_key = getattr(settings, "huggingface_api_key", "")
    if hf_key:
        return _HFLLM(hf_key), "huggingface-llama-3.2"
    raise RuntimeError("No operational LLM providers configured for Composer Agent")


# ─── Cleaning Logic ────────────────────────────────────────────


def _clean_output(raw: str) -> str:
    """Strips out conversational markdown scaffolding and formatting blocks."""
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].lstrip()
            if "\n" in text and text.split("\n", 1)[0].lower() in (
                "markdown",
                "text",
                "",
            ):
                text = text.split("\n", 1)[1]

    text = re.sub(
        r"^(here['']?s the post[:\-]?|post[:\-]|output[:\-]|response[:\-])\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    if len(text) > 2 and text[0] in ('"', "'") and text[-1] == text[0]:
        text = text[1:-1].strip()
    return text.strip()


# ─── Concurrent Worker Task ────────────────────────────────────


async def _generate_draft_task(
    llm: Any, system_prompt: str, user_prompt: str, draft_number: int
) -> dict[str, Any] | None:
    """Runs a single targeted draft instantiation with variance adjustment parameters."""
    # Instruct the model dynamically on how to branch its narrative structure
    variance_prompts = {
        1: "\n\nStyle Guide: Focus on a strong linear structural narrative with immediate value delivery.",
        2: "\n\nStyle Guide: Focus on an inductive format—present strong concrete observations first, then abstract rules.",
        3: "\n\nStyle Guide: Focus on a conversational, highly engaging rhythmic cadence with varied paragraph breaks.",
    }

    modified_system = system_prompt + variance_prompts.get(draft_number, "")

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=modified_system),
                HumanMessage(content=user_prompt),
            ]
        )
        content = _clean_output(response.content)

        if not content:
            return None

        return {
            "draft_number": draft_number,
            "platform": "Multi-Variant Draft",
            "content": content,
            "char_count": len(content),
        }
    except Exception as exc:
        logger.warning(
            f"[composer] Parallel task variant #{draft_number} execution failed: {exc}"
        )
        return None


# ─── LangGraph Runtime Core Node ───────────────────────────────


async def composer_node(state: MemoryState) -> dict[str, Any]:
    run_id = state.get("run_id", "unknown")
    prompt = (state.get("user_prompt") or "").strip()
    persona = state.get("personalization") or {}
    research = state.get("research_data") or {}
    platform = state.get("target_platform") or "Web"
    tone = state.get("tone") or "Casual"
    content_length = state.get("content_length") or "Medium"
    completed = state.get("agents_completed", [])

    pages = research.get("fetched_pages", [])

    # Gracefully capture complete execution if research stack completely bypassed data
    if not pages:
        logger.warning(
            "Composer agent invoked without primary research data pages", run_id
        )

    try:
        llm, llm_name = await _pick_llm()
    except RuntimeError as exc:
        logger.error(f"Composer system failure: {exc}", run_id)
        return {
            "composer_output": [],
            "current_agent": "composer",
            "agents_completed": [*completed, "composer"],
            "error": str(exc),
        }

    # Construct the advanced system and context matrices
    system_prompt = build_composer_system_prompt(
        platform, tone, content_length, persona
    )
    user_prompt = build_composer_user_prompt(prompt, pages)

    # Concurrently execute all three drafts over your provider engine pipelines
    start_time = time.time()
    tasks = [
        _generate_draft_task(llm, system_prompt, user_prompt, i) for i in range(1, 4)
    ]
    executed_drafts = await asyncio.gather(*tasks)
    latency_ms = int((time.time() - start_time) * 1000)

    # Filter out any failed task slices cleanly
    final_outputs = [draft for draft in executed_drafts if draft is not None]

    logger.info(
        f"☲ COMPOSER COMPLETE: Produced {len(final_outputs)} drafts via {llm_name} in {latency_ms}ms",
        run_id,
    )

    # Extract clean references for metadata state mapping
    source_references = [
        {
            "title": p.get("title", "Untitled Source"),
            "url": p.get("url"),
            "domain": p.get("domain"),
            "rank_score": p.get("rank_score", 1.0),
        }
        for p in pages[:4]
    ]

    return {
        "composer_output": final_outputs,
        "composer_sources": source_references,
        "current_agent": "composer",
        "agents_completed": [*completed, "composer"],
        "error": None
        if final_outputs
        else "All parallel composition streams failed to generate text.",
    }


def build_composer_graph() -> StateGraph:
    builder = StateGraph(MemoryState)
    builder.add_node("run", composer_node)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder
