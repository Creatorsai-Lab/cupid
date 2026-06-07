"""
Personalization Agent — query decomposition for content research.

Decomposes a creator's topic into 5 orthogonal search queries covering
distinct retrieval angles, strictly tailored to their niche and tone.

Provider order (first available wins):
    1. Groq (Llama 3.3 70B)       — primary, very fast
    2. Hugging Face Inference API — fallback AI
    3. Local heuristic            — last resort, zero-LLM
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Protocol

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.agents.state import MemoryState
from app.agents.personalization.local_heuristic import generate_queries as heuristic_queries
from app.config import settings
from app.core.logging_config import get_agent_logger

logger = get_agent_logger("personalization")

# ─── Prompting ───────────────────────────────────────────────────

def _build_system_prompt(niche: str, tone: str, audience: str, region: str) -> str:
    year = datetime.now().year
    return f"""\
You are an expert search query strategist for social media creators. 
Your job is to generate exactly 5 highly profile persoanlized search queries to feed a downstream research agent. 
Tailor the queries specifically understanding the user input prompt and his intent to create content. Goal is to create queries using that research pipeline collect most relevent and personalized contents.

### CREATOR PROFILE
- Niche/Vocabulary: {niche or 'General Content Creation'}
- Tone/Style: {tone or 'Informative'}
- Target Region: {region or 'Global'}

### THE 5 RETRIEVAL ANGLES (One query per angle):
Decode the user input and intent with 5 angles

### QUERY RULES:
- 4 to 9 words each. Use concrete nouns over adjectives.
- YOU MUST bake the creator's specific niche vocabulary and tone into the queries. 
- Anchor on specific entities, tools, people, or proper nouns.
- No question marks. No quotes. No site: operators. No numbering. 
- Queries must NOT overlap.

OUTPUT FORMAT (STRICT):
Return ONLY a JSON array of 5 strings. No prose, no markdown, no code fences.
Example: ["query one","query two","query three","query four","query five"]"""


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
            temperature=0.4,
            max_tokens=350,
            timeout=12,
        )

    async def generate(self, system: str, user: str) -> list[str]:
        response = await self.llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=user),
        ])
        return _parse_queries(response.content)


class HuggingFaceProvider:
    name = "huggingface-llama-3.2"

    def __init__(self, api_key: str, model: str = "meta-llama/Llama-3.2-3B-Instruct") -> None:
        self.api_key = api_key
        self.model = model
        self.url = f"https://api-inference.huggingface.co/models/{model}"

    async def generate(self, system: str, user: str) -> list[str]:
        combined = f"<|system|>\n{system}\n<|user|>\n{user}\n<|assistant|>\n"
        payload = {
            "inputs": combined,
            "parameters": {"max_new_tokens": 350, "temperature": 0.4, "return_full_text": False},
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self.url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text = data[0].get("generated_text", "") if isinstance(data, list) and data else ""
        return _parse_queries(text)


class HeuristicProvider:
    name = "heuristic-local"

    async def generate(self, system: str, user: str) -> list[str]:
        # The prompt is passed via user message as "TOPIC: <prompt>"
        topic = user.replace("TOPIC:", "").strip()
        return heuristic_queries(topic)


# ─── Parsing ─────────────────────────────────────────────────────

def _parse_queries(raw: str) -> list[str]:
    """Extract queries from the structured JSON output."""
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].removeprefix("json").strip()

    try:
        parsed = json.loads(text)
        queries = []
        if isinstance(parsed, dict) and "queries" in parsed:
            queries = parsed["queries"]
        elif isinstance(parsed, list):
            queries = parsed
            
        clean_queries = [str(q).strip() for q in queries if str(q).strip()]
        if clean_queries:
            return _dedupe(clean_queries)[:5]
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback parsing if LLM fails JSON constraint
    lines = [line.lstrip("-*•0123456789. \t").strip().strip('"\'') for line in text.splitlines()]
    queries = [line for line in lines if line and len(line.split()) >= 3 and "reasoning" not in line.lower()]
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
            logger.warning(f"[personalization] Groq disabled: {str(exc)[:100]}")

    hf_key = getattr(settings, "huggingface_api_key", "")
    if hf_key:
        try:
            chain.append(HuggingFaceProvider(hf_key))
        except Exception as exc:
            logger.warning(f"[personalization] HF disabled: {str(exc)[:100]}")

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
            logger.warning(f"[personalization] {provider.name} failed: {str(exc)[:100]}")
            continue
    return [], "none"


# ─── LangGraph node ──────────────────────────────────────────────

async def personalization_node(state: MemoryState) -> dict[str, Any]:
    run_id = state.get("run_id", "unknown")
    prompt = (state.get("user_prompt") or "").strip()
    persona = state.get("personalization") or {}
    completed = state.get("agents_completed", [])

    if not prompt:
        return {"personalization_queries": [], "current_agent": "personalization", "agents_completed": [*completed, "personalization"]}

    # Extract high-value parameters ONLY
    niche = persona.get("content_niche", "")
    tone = persona.get("tone", "")  # From frontend TONE const
    audience = persona.get("target_audience", "")
    region = persona.get("target_country", "")

    system_msg = _build_system_prompt(niche, tone, audience, region)
    user_msg = f"TOPIC: {prompt}"
    
    start_time = time.time()
    queries, provider_used = await _run_chain(system_msg, user_msg)
    latency_ms = int((time.time() - start_time) * 1000)

    logger.info(f"📋 GENERATED QUERIES ({provider_used}):", run_id)
    for i, q in enumerate(queries, 1):
        logger.info(f"  [{i}] → {q}", run_id)

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