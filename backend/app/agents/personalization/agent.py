"""
Personalization Agent — query decomposition for content research.

Decomposes a creator's topic into 5 orthogonal search queries covering
distinct retrieval angles, strictly tailored to their niche and intent.

Provider order (first available wins):
    1. Groq (Llama 3.3 70B)       — primary, very fast
    2. Hugging Face Inference API — fallback AI
    3. Local heuristic            — last resort, zero-LLM
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any, Protocol

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.agents.personalization.local_heuristic import (
    generate_queries as heuristic_queries,
)
from app.agents.state import MemoryState
from app.config import settings
from app.core.logging_config import get_agent_logger

logger = get_agent_logger("personalization")

# ─── Prompting ───────────────────────────────────────────────────


def _build_system_prompt(niche: str, tone: str, region: str) -> str:
    year = datetime.now().year
    return f"""\
You are an expert search query strategist for social media content research. Your job is to decompose a raw content topic into exactly 6-7 highly-targeted search queries for a downstream web search retrieval agent.

### THE CORE INTENT RULE (CRITICAL)
Do NOT include tonal slang, adjectives, or meta-commentary (e.g., "comedy", "funny", "viral", "genz", "hilarious", "joke", "hooks") inside the search queries. Search engines fail when queried with emotional or stylistic modifiers.
Instead, translate the creator's tone into the *type of high-signal information* required:
- Start with understanding what is main piece of content user want to create with its prompt
- If Tone is "Data Driven", "Factual", or "Formal": Focus queries on benchmarks, statistics, documentation, and industry standards.
- If Tone is "GenZ", "Casual", "Hook First", or "Story Led": Focus queries on real-world case studies, dramatic failures, unexpected counter-intuitive findings, and tangible anecdotes.

### CREATOR PROFILE
- Niche/Vocabulary: {niche or "General Content Creation"}
- Target Tone: {tone or "Informative"}
- Target Region: {region or "Global"} unless user mention specific location
- Current Year: {year}

### THE DIFFERENT RETRIEVAL PERSPECTIVES
Decompose the input topic  fewnon-overlapping search vectors and few supporting search vector. Understand the perspective of user input prompt, for example
1. CORE MECHANICS: Fundamental required, how it works under the hood, or technical baselines.
2. Main content piece user want to show to his audience
3. CURRENT TRENDS: Fresh updates, Add the current year {year} if necessary, unless a specific time period is mentioned in the user input, look hot topics, or modern changes in this space.
4. You can also focus on related sub micro topic under user input topic
5. Create 3 more personalized perspective on user prompt

### QUERY RULES:
- 4 to 9 words per query. Use concrete, high-signal nouns over descriptive adjectives.
- Keep queries pure for search engine entry: No question marks, no quotes, no numbering.
- Concentrate on creating queries to ensure the web retrieval team gets web content perfectly matched to user topic intent.

### OUTPUT FORMAT (STRICT):
Return ONLY a valid JSON array containing exactly 5 strings. No markdown code blocks, no explanation text before or after.
Example: ["query one","query two","query three","query four","query five", "query six", "query seven"]"""


# ─── Provider interface ──────────────────────────────────────────


class QueryProvider(Protocol):
    name: str

    async def generate(self, system: str, user: str) -> list[str]: ...


class GroqProvider:
    name = "groq-llama-3.3-70b"

    def __init__(self, api_key: str) -> None:
        from langchain_groq import ChatGroq

        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            groq_api_key=api_key,
            temperature=0.3,
            max_tokens=250,
            timeout=12,
        )

    async def generate(self, system: str, user: str) -> list[str]:
        response = await self.llm.ainvoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=user),
            ]
        )
        return _parse_queries(response.content)


class HuggingFaceProvider:
    name = "huggingface-llama-3.2"

    def __init__(
        self, api_key: str, model: str = "meta-llama/Llama-3.2-3B-Instruct"
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.url = f"https://api-inference.huggingface.co/models/{model}"

    async def generate(self, system: str, user: str) -> list[str]:
        combined = f"<|system|>\n{system}\n<|user|>\n{user}\n<|assistant|>\n"
        payload = {
            "inputs": combined,
            "parameters": {
                "max_new_tokens": 250,
                "temperature": 0.3,
                "return_full_text": False,
            },
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self.url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text = (
            data[0].get("generated_text", "") if isinstance(data, list) and data else ""
        )
        return _parse_queries(text)


class HeuristicProvider:
    name = "heuristic-local"

    async def generate(self, system: str, user: str) -> list[str]:
        topic = user.replace("TOPIC:", "").strip()
        return heuristic_queries(topic)


# ─── Parsing ─────────────────────────────────────────────────────


def _parse_queries(raw: str) -> list[str]:
    """Clean up and safely parse raw text outputs into a strict string list."""
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].removeprefix("json").strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            clean_queries = [str(q).strip() for q in parsed if str(q).strip()]
            if clean_queries:
                return _dedupe(clean_queries)[:5]
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback line-by-line parsing if JSON block format got slightly corrupted
    lines = [
        line.lstrip("-*•0123456789. \t").strip().strip("\"'")
        for line in text.splitlines()
    ]
    queries = [line for line in lines if line and len(line.split()) >= 3]
    return _dedupe(queries)[:5]


def _dedupe(queries: list[str]) -> list[str]:
    seen, out = set(), []
    for q in queries:
        key = " ".join(q.lower().split())
        if key not in seen:
            seen.add(key)
            out.append(q)
    return out


# ─── Provider chain ──────────────────────────────────────────────


def _build_provider_chain() -> list[QueryProvider]:
    chain: list[QueryProvider] = []

    groq_key = getattr(settings, "groq_api_key", "")
    if groq_key:
        try:
            chain.append(GroqProvider(groq_key))
        except Exception as exc:
            logger.warning(
                f"[personalization] Groq initialization skipped: {str(exc)[:100]}"
            )

    hf_key = getattr(settings, "huggingface_api_key", "")
    if hf_key:
        try:
            chain.append(HuggingFaceProvider(hf_key))
        except Exception as exc:
            logger.warning(
                f"[personalization] HF initialization skipped: {str(exc)[:100]}"
            )

    chain.append(HeuristicProvider())
    return chain


async def _run_chain(system: str, user: str) -> tuple[list[str], str]:
    chain = _build_provider_chain()
    for provider in chain:
        try:
            queries = await provider.generate(system, user)
            if len(queries) >= 3:
                return queries, provider.name
        except Exception as exc:
            logger.warning(
                f"[personalization] {provider.name} execution failed: {str(exc)[:100]}"
            )
            logger.warning(
                f"[personalization] {provider.name} execution failed: {str(exc)[:100]}"
            )
            continue
    return [], "none"


# ─── LangGraph node ──────────────────────────────────────────────


async def personalization_node(state: MemoryState) -> dict[str, Any]:
    # run_id = state.get("run_id", "unknown")
    prompt = (state.get("user_prompt") or "").strip()
    persona = state.get("personalization") or {}
    completed = state.get("agents_completed", [])

    if not prompt:
        return {
            "personalization_queries": [],
            "current_agent": "personalization",
            "agents_completed": [*completed, "personalization"],
        }

    niche = persona.get("content_niche", "")
    tone = persona.get("tone", "")
    region = persona.get("target_country", "")

    system_msg = _build_system_prompt(niche, tone, region)
    user_msg = f"USER INPUT PROMPT: {prompt}"

    time.time()
    queries, provider_used = await _run_chain(system_msg, user_msg)

    # logger.info("📋 MOE SEARCH GENERATION (%s):", provider_used, run_id)
    # for i, q in enumerate(queries, 1):
    #     logger.info(f"  [{i}] → {q}", run_id)

    return {
        "personalization_queries": queries,
        "current_agent": "personalization",
        "agents_completed": [*completed, "personalization"],
    }


def build_personalization_graph() -> StateGraph:
    builder = StateGraph(MemoryState)
    builder.add_node("run", personalization_node)
    builder.set_entry_point("run")
    builder.add_edge("run", END)
    return builder
