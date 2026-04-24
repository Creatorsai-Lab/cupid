"""
Evidence Distiller — extract atomic facts from top sources.

Single LLM call that reads the top 3 ranked sources and produces a
structured list of facts (stats, quotes, entities, claims) that the
composer variants can reference. This is the "grounding layer" that
prevents hallucination.

Why one call instead of per-source?
    - Cheaper (1 call vs 3)
    - LLM can deduplicate across sources
    - Produces a unified fact list with source attribution
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a research assistant. Your job is to extract ATOMIC FACTS from source material.

An atomic fact is:
- A single, verifiable claim
- Attributed to a specific source
- Categorized by type (stat, quote, entity, claim, relationship)

TYPES:
- stat: A number, percentage, or quantitative claim
- quote: A direct statement from a person or document
- entity: A named person, company, product, or place
- claim: A qualitative assertion (e.g., "X is the leading Y")
- relationship: A connection between two entities (e.g., "X acquired Y")

RULES:
- Extract 5-12 facts total across all sources
- Prioritize surprising or specific information
- Do NOT paraphrase quotes — keep them verbatim
- Do NOT invent facts not present in the sources
- Attribute each fact to its source number (0, 1, 2, etc.)

OUTPUT FORMAT (JSON array):
[
  {"fact": "...", "source": 0, "type": "stat"},
  {"fact": "...", "source": 1, "type": "quote"},
  ...
]

Return ONLY the JSON array. No preamble, no markdown fences, no explanation.
"""


def _build_sources_block(sources: list[dict[str, Any]]) -> str:
    """Format the top sources into a numbered list for the LLM."""
    lines = []
    for i, src in enumerate(sources):
        title = src.get("title", "Untitled")
        domain = src.get("domain", "unknown")
        text = src.get("text_content", "")[:2000]  # cap at 2k chars per source
        lines.append(f"[SOURCE {i}] {title} ({domain})\n{text}\n")
    return "\n".join(lines)


async def distill_evidence(
    llm: Any,
    user_prompt: str,
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Extract atomic facts from the top sources.

    Args:
        llm: LangChain-compatible LLM (must support .ainvoke([messages]))
        user_prompt: user's original content request (for context)
        sources: top 3 ranked pages from source_ranker

    Returns:
        List of fact dicts: [{"fact": str, "source": int, "type": str}, ...]
    """
    if not sources:
        logger.warning("[evidence_distiller] no sources provided")
        return []

    sources_block = _build_sources_block(sources)
    user_message = (
        f"USER REQUEST\n{user_prompt}\n\n"
        f"SOURCES\n{sources_block}\n\n"
        f"Extract the atomic facts now."
    )

    try:
        response = await llm.ainvoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ])
        raw = response.content.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        facts = json.loads(raw)

        if not isinstance(facts, list):
            logger.warning("[evidence_distiller] LLM returned non-list: %s", type(facts))
            return []

        # Validate structure
        valid_facts = []
        for f in facts:
            if isinstance(f, dict) and "fact" in f and "source" in f and "type" in f:
                valid_facts.append({
                    "fact": str(f["fact"]),
                    "source": int(f["source"]),
                    "type": str(f["type"]),
                })

        logger.info("[evidence_distiller] extracted %d facts", len(valid_facts))
        return valid_facts

    except json.JSONDecodeError as exc:
        logger.error("[evidence_distiller] JSON parse failed: %s", exc)
        logger.debug("[evidence_distiller] raw output: %s", raw[:500])
        return []
    except Exception as exc:
        logger.error("[evidence_distiller] failed: %s", exc, exc_info=True)
        return []
