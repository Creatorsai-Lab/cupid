"""
Source Ranker — pick the top K sources from research output.

No LLM calls. Uses classical IR (BM25) + persona-aware boosting to
rank the N pages fetched by the Research Agent and return only the
most relevant ones. This prevents context bloat in the composer prompt.
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-\+\.#]*")

_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "should", "could", "may", "might", "can", "i",
    "you", "we", "they", "it", "of", "in", "on", "at", "for", "with",
    "by", "from", "about", "as", "to", "this", "that", "these", "those",
    "what", "which", "who", "when", "where", "why", "how",
})

# Domain authority bonuses — trust signal, not ground truth
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
    """
    Classic BM25. Given a query (flat list of tokens) and a document
    (flat list of tokens), returns the relevance score.
    """
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
    return min(overlap * 0.03, 0.20)  # cap at +0.20


def _build_query_string(
    user_prompt: str,
    personalization: dict[str, Any],
) -> str:
    """Concatenate prompt + persona signals into a single query."""
    parts = [user_prompt]
    for key in ("content_niche", "target_audience", "usp"):
        val = personalization.get(key)
        if val:
            parts.append(str(val))
    return " ".join(parts)


def _build_persona_terms(personalization: dict[str, Any]) -> set[str]:
    """Extract the vocabulary we expect the persona to care about."""
    fields = [
        personalization.get("content_niche", ""),
        personalization.get("target_audience", ""),
        personalization.get("content_intent", ""),
        personalization.get("usp", ""),
        personalization.get("bio", ""),
    ]
    return set(_tokenize(" ".join(str(f) for f in fields if f)))


def rank_sources(
    pages: list[dict[str, Any]],
    user_prompt: str,
    personalization: dict[str, Any] | None = None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """
    Rank `pages` against the user's intent + persona. Return top K.

    Args:
        pages: fetched_pages from research_data. Each needs
            text_content, title, domain.
        user_prompt: user's raw content request.
        personalization: creator profile (niche, audience, USP, etc.).
        top_k: how many top sources to return.

    Returns:
        Top K pages with an added `rank_score` field, highest first.
    """
    if not pages:
        return []

    persona = personalization or {}
    query_str = _build_query_string(user_prompt, persona)
    persona_terms = _build_persona_terms(persona)
    query_terms = _tokenize(query_str)

    # Pre-compute corpus statistics for BM25
    tokenized_docs: list[list[str]] = []
    for page in pages:
        text = f"{page.get('title', '')} {page.get('text_content', '')}"
        tokenized_docs.append(_tokenize(text))

    if not any(tokenized_docs):
        logger.warning("[source_ranker] all documents empty after tokenization")
        return pages[:top_k]

    avg_doc_len = sum(len(d) for d in tokenized_docs) / len(tokenized_docs)
    doc_freqs: Counter[str] = Counter()
    for doc_terms in tokenized_docs:
        doc_freqs.update(set(doc_terms))

    # Score every page
    scored: list[tuple[float, dict[str, Any]]] = []
    for page, doc_terms in zip(pages, tokenized_docs, strict=True):
        bm25 = _bm25_score(
            query_terms, doc_terms, avg_doc_len, len(pages), doc_freqs,
        )
        auth = _authority_bonus(page.get("domain", ""))
        persona_b = _persona_boost(page, persona_terms)

        # Normalize BM25 into 0-1 range (approximate — BM25 is unbounded)
        bm25_norm = bm25 / (bm25 + 3.0)
        total = bm25_norm + auth + persona_b

        scored_page = {**page, "rank_score": round(total, 4)}
        scored.append((total, scored_page))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [page for _, page in scored[:top_k]]

    logger.info(
        "[source_ranker] picked top %d of %d — scores: %s",
        len(top), len(pages),
        [round(s, 3) for s, _ in scored[:top_k]],
    )
    return top