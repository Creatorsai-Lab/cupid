"""
Composer Utilities — consolidated source ranking, evidence extraction, and quality scoring.

This module combines three previously separate concerns into a single, cohesive utility layer:
    1. SOURCE RANKING  — BM25 + persona-aware boosting to pick top K sources
    2. EVIDENCE DISTILLATION — LLM-based atomic fact extraction from sources
    3. QUALITY SCORING — multi-axis deterministic evaluation of composed variants

All functions are stateless and can be called independently.
"""
from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.composer.platform_rules import PlatformRule

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE RANKING — BM25 + persona boosting
# ═══════════════════════════════════════════════════════════════════════════════

_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-\+\.#]*")

_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "should", "could", "may", "might", "can", "i",
    "you", "we", "they", "it", "of", "in", "on", "at", "for", "with",
    "by", "from", "about", "as", "to", "this", "that", "these", "those",
    "what", "which", "who", "when", "where", "why", "how",
})

_AUTHORITY_BONUS: dict[str, float] = {
    ".gov": 0.25,
    ".edu": 0.25,
    ".org": 0.10,
    "arxiv.org": 0.20,
    "github.com": 0.15,
    "docs.python.org": 0.15,
    "wikipedia.org": 0.12,
    "stackoverflow.com": 0.10,
}


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip stopwords and short tokens."""
    return [
        tok for tok in (m.group().lower() for m in _WORD_RE.finditer(text))
        if tok not in _STOPWORDS and len(tok) > 2
    ]


def _bm25_score(
    query_terms: list[str],
    doc_terms: list[str],
    avg_doc_len: float,
    corpus_size: int,
    doc_freqs: Counter[str],
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    """Classic BM25 relevance scoring."""
    if not doc_terms or not query_terms:
        return 0.0

    doc_len = len(doc_terms)
    doc_tf = Counter(doc_terms)
    score = 0.0

    for term in query_terms:
        if term not in doc_tf:
            continue
        tf = doc_tf[term]
        df = doc_freqs.get(term, 1)
        idf = math.log((corpus_size - df + 0.5) / (df + 0.5) + 1.0)
        norm = tf * (k1 + 1) / (tf + k1 * (1 - b + b * doc_len / max(avg_doc_len, 1)))
        score += idf * norm

    return score


def _authority_bonus(domain: str) -> float:
    """Return the largest applicable authority bonus for this domain."""
    best = 0.0
    for suffix, bonus in _AUTHORITY_BONUS.items():
        if domain.endswith(suffix) and bonus > best:
            best = bonus
    return best


def _persona_boost(page: dict[str, Any], persona_terms: set[str]) -> float:
    """Bonus when page content overlaps with persona-specific vocabulary."""
    if not persona_terms:
        return 0.0
    text = (page.get("title", "") + " " + page.get("text_content", ""))[:2000]
    page_terms = set(_tokenize(text))
    overlap = len(persona_terms & page_terms)
    return min(overlap * 0.03, 0.20)


def rank_sources(
    pages: list[dict[str, Any]],
    user_prompt: str,
    personalization: dict[str, Any] | None = None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """
    Rank pages using BM25 + persona + authority signals. Return top K.

    Args:
        pages: fetched_pages from research_data (needs text_content, title, domain)
        user_prompt: user's raw content request
        personalization: creator profile (niche, audience, USP, etc.)
        top_k: how many top sources to return

    Returns:
        Top K pages with added `rank_score` field, highest first
    """
    if not pages:
        return []

    persona = personalization or {}
    
    # Build query from prompt + persona
    query_parts = [user_prompt]
    for key in ("content_niche", "target_audience", "usp"):
        val = persona.get(key)
        if val:
            query_parts.append(str(val))
    query_str = " ".join(query_parts)
    
    # Extract persona vocabulary
    persona_fields = [
        persona.get("content_niche", ""),
        persona.get("target_audience", ""),
        persona.get("content_intent", ""),
        persona.get("usp", ""),
        persona.get("bio", ""),
    ]
    persona_terms = set(_tokenize(" ".join(str(f) for f in persona_fields if f)))
    
    query_terms = _tokenize(query_str)

    # Tokenize all documents
    tokenized_docs: list[list[str]] = []
    for page in pages:
        text = f"{page.get('title', '')} {page.get('text_content', '')}"
        tokenized_docs.append(_tokenize(text))

    if not any(tokenized_docs):
        logger.warning("[rank_sources] all documents empty after tokenization")
        return pages[:top_k]

    # Compute BM25 corpus statistics
    avg_doc_len = sum(len(d) for d in tokenized_docs) / len(tokenized_docs)
    doc_freqs: Counter[str] = Counter()
    for doc_terms in tokenized_docs:
        doc_freqs.update(set(doc_terms))

    # Score every page
    scored: list[tuple[float, dict[str, Any]]] = []
    for page, doc_terms in zip(pages, tokenized_docs, strict=True):
        bm25 = _bm25_score(query_terms, doc_terms, avg_doc_len, len(pages), doc_freqs)
        auth = _authority_bonus(page.get("domain", ""))
        persona_b = _persona_boost(page, persona_terms)

        # Normalize BM25 into 0-1 range (approximate)
        bm25_norm = bm25 / (bm25 + 3.0)
        total = bm25_norm + auth + persona_b

        scored_page = {**page, "rank_score": round(total, 4)}
        scored.append((total, scored_page))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [page for _, page in scored[:top_k]]

    logger.info(
        "[rank_sources] picked top %d of %d — scores: %s",
        len(top), len(pages), [round(s, 3) for s, _ in scored[:top_k]],
    )
    return top


# ═══════════════════════════════════════════════════════════════════════════════
# EVIDENCE DISTILLATION — atomic fact extraction
# ═══════════════════════════════════════════════════════════════════════════════

_EVIDENCE_SYSTEM_PROMPT = """\
You are a research assistant. Extract ATOMIC FACTS from source material.

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


async def distill_evidence(
    llm: Any,
    user_prompt: str,
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Extract atomic facts from top sources using LLM.

    Args:
        llm: LangChain-compatible LLM (must support .ainvoke([messages]))
        user_prompt: user's original content request (for context)
        sources: top ranked pages from rank_sources

    Returns:
        List of fact dicts: [{"fact": str, "source": int, "type": str}, ...]
    """
    if not sources:
        logger.warning("[distill_evidence] no sources provided")
        return []

    # Format sources for LLM
    sources_block = []
    for i, src in enumerate(sources):
        title = src.get("title", "Untitled")
        domain = src.get("domain", "unknown")
        text = src.get("text_content", "")[:2000]  # cap at 2k chars per source
        sources_block.append(f"[SOURCE {i}] {title} ({domain})\n{text}\n")
    
    user_message = (
        f"USER REQUEST\n{user_prompt}\n\n"
        f"SOURCES\n{chr(10).join(sources_block)}\n\n"
        f"Extract the atomic facts now."
    )

    try:
        response = await llm.ainvoke([
            SystemMessage(content=_EVIDENCE_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ])
        raw = response.content.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        facts = json.loads(raw)

        if not isinstance(facts, list):
            logger.warning("[distill_evidence] LLM returned non-list: %s", type(facts))
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

        logger.info("[distill_evidence] extracted %d facts", len(valid_facts))
        return valid_facts

    except json.JSONDecodeError as exc:
        logger.error("[distill_evidence] JSON parse failed: %s", exc)
        logger.debug("[distill_evidence] raw output: %s", raw[:500])
        return []
    except Exception as exc:
        logger.error("[distill_evidence] failed: %s", exc, exc_info=True)
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# QUALITY SCORING — multi-axis evaluation
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class QualityScore:
    length_fit: float
    grounding: float
    persona_match: float
    hook_strength: float
    composite: float
    passes_threshold: bool


_WEIGHTS = {
    "length_fit": 0.20,
    "grounding": 0.35,
    "persona_match": 0.20,
    "hook_strength": 0.25,
}

_MIN_COMPOSITE = 0.45

_NUMBER_RE = re.compile(r"\b\d[\d.,%]*\b")

_WEAK_OPENERS = frozenset({
    "in", "as", "today", "nowadays", "in today's", "let's", "so,", "well,",
    "first", "firstly", "have", "did", "are", "here's", "heres",
})


def _tokenize_for_scoring(text: str) -> set[str]:
    """Tokenize and remove stopwords for quality scoring."""
    tokens = re.findall(r"[A-Za-z][A-Za-z\-]+", text.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 2}


def _score_length(content: str, rule: PlatformRule) -> float:
    """1.0 at target, 0.0 below min or above max, linear between."""
    length = len(content)
    if length < rule.min_chars or length > rule.max_chars:
        return 0.0
    target = rule.target_chars
    if length <= target:
        bound_dist = target - rule.min_chars
        return 1.0 - (target - length) / max(bound_dist, 1)
    else:
        bound_dist = rule.max_chars - target
        return 1.0 - (length - target) / max(bound_dist, 1)


def _score_grounding(content: str, facts: list[dict[str, Any]]) -> float:
    """Check if post references distilled evidence (numbers, keywords)."""
    if not facts:
        return 0.7  # neutral when no facts available

    content_tokens = _tokenize_for_scoring(content)
    content_numbers = set(_NUMBER_RE.findall(content))

    fact_numbers: set[str] = set()
    fact_tokens: set[str] = set()
    for f in facts:
        fact_text = f.get("fact", "")
        fact_numbers.update(_NUMBER_RE.findall(fact_text))
        fact_tokens.update(_tokenize_for_scoring(fact_text))

    # Number match is strongest grounding signal
    number_overlap = len(content_numbers & fact_numbers) / max(len(fact_numbers), 1)
    keyword_overlap = len(content_tokens & fact_tokens) / max(len(fact_tokens), 1)
    has_any_number = 1.0 if content_numbers else 0.0

    score = 0.5 * number_overlap + 0.3 * keyword_overlap + 0.2 * has_any_number
    return min(score, 1.0)


def _score_persona_match(content: str, personalization: dict[str, Any]) -> float:
    """Lexical overlap between post and persona vocabulary."""
    persona_text = " ".join(
        str(personalization.get(k, ""))
        for k in ("bio", "usp", "content_niche", "target_audience")
    ).strip()
    if not persona_text:
        return 0.7  # neutral when no persona data

    content_tokens = _tokenize_for_scoring(content)
    persona_tokens = _tokenize_for_scoring(persona_text)
    if not persona_tokens:
        return 0.7

    overlap = len(content_tokens & persona_tokens)
    return min(overlap / 3.0, 1.0)  # saturating curve


def _score_hook_strength(content: str) -> float:
    """Heuristics for first-line quality."""
    first_line = content.strip().split("\n", 1)[0].strip()
    if not first_line:
        return 0.0

    score = 0.5  # baseline

    first_words = first_line.lower().split()
    if not first_words:
        return 0.0

    # Weak opener penalty
    first_two = " ".join(first_words[:2])
    if first_words[0] in _WEAK_OPENERS or first_two in _WEAK_OPENERS:
        score -= 0.25

    # Specificity bonus
    if _NUMBER_RE.search(first_line):
        score += 0.20
    proper_nouns = sum(
        1 for w in first_line.split()[1:] if w and w[0].isupper() and len(w) > 2
    )
    if proper_nouns >= 1:
        score += 0.15

    # Punchiness bonus
    word_count = len(first_words)
    if 3 <= word_count <= 12:
        score += 0.15
    elif word_count > 25:
        score -= 0.15

    # Question hook
    if "?" in first_line:
        score += 0.10

    return max(0.0, min(score, 1.0))


def score_variant(
    content: str,
    facts: list[dict[str, Any]],
    personalization: dict[str, Any],
    rule: PlatformRule,
) -> QualityScore:
    """Score one composed variant on all four axes."""
    length_fit = _score_length(content, rule)
    grounding = _score_grounding(content, facts)
    persona_match = _score_persona_match(content, personalization)
    hook_strength = _score_hook_strength(content)

    composite = (
        _WEIGHTS["length_fit"] * length_fit
        + _WEIGHTS["grounding"] * grounding
        + _WEIGHTS["persona_match"] * persona_match
        + _WEIGHTS["hook_strength"] * hook_strength
    )

    return QualityScore(
        length_fit=round(length_fit, 3),
        grounding=round(grounding, 3),
        persona_match=round(persona_match, 3),
        hook_strength=round(hook_strength, 3),
        composite=round(composite, 3),
        passes_threshold=composite >= _MIN_COMPOSITE,
    )
