"""
Personalization Ranker — re-orders pre-fetched articles for one user.

This is where the "personalized" in "personalized trends" actually happens.
Two articles can both be in the user's category, but one might mention
their specific subniche, audience, or USP terms. That one ranks higher.

Algorithm:
    final_score = α·relevance + β·velocity + γ·recency

    where:
      relevance = BM25(article_text, persona_keywords)
      velocity  = pre-computed at ingestion (source authority + recency)
      recency   = decay function over hours since publication

We use BM25 over IR-classic over embeddings because:
    - Determinism: same persona + same article = same score, every time
    - Speed: zero LLM calls, all in-process
    - No embedding model dependency (yet)
    - Plenty good for sub-100-article corpora
"""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any


# ──────────────────────────────────────────────────────────────────
#  Tokenization
# ──────────────────────────────────────────────────────────────────

_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-\+\.#]*")

_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "i", "you", "we", "they", "it", "of", "in", "on",
    "at", "for", "with", "by", "from", "about", "as", "to", "this",
    "that", "these", "those", "what", "which", "who", "when", "where",
    "why", "how", "more", "most", "some", "such", "now", "new",
})


def _tokenize(text: str) -> list[str]:
    """Lowercase, drop stopwords, keep terms ≥3 chars."""
    return [
        m.group().lower()
        for m in _WORD_RE.finditer(text)
        if len(m.group()) >= 3 and m.group().lower() not in _STOPWORDS
    ]


# ──────────────────────────────────────────────────────────────────
#  Persona vocabulary extraction
# ──────────────────────────────────────────────────────────────────

def _persona_terms(persona: dict[str, Any]) -> set[str]:
    """
    Pull the vocabulary that signals this user's interests.

    These four fields together tell us what they care about. We don't
    weight them differently here — every match counts. If we found that
    USP overlap is more predictive than audience overlap (via A/B test),
    we'd add per-field weights here.
    """
    parts: list[str] = []
    for field in ("content_niche", "target_audience", "usp", "bio"):
        value = persona.get(field)
        if value:
            parts.append(str(value))
    return set(_tokenize(" ".join(parts)))


# ──────────────────────────────────────────────────────────────────
#  BM25 — the core information retrieval algorithm
# ──────────────────────────────────────────────────────────────────
#
# In one sentence: BM25 scores how well a query matches a document while
# accounting for how rare each query term is in the corpus and how long
# the document is.
#
# Key intuition:
#   - A term that appears in every document is uninformative (low IDF).
#   - A term repeated 100x in one doc isn't 100x more relevant than once.
#   - A 5000-word doc shouldn't beat a 500-word doc just by length.

def _bm25(
    query_terms: set[str],
    doc_terms: list[str],
    avg_doc_len: float,
    corpus_size: int,
    doc_freqs: Counter[str],
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    """Standard BM25 scoring. k1 and b are textbook defaults."""
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


# ──────────────────────────────────────────────────────────────────
#  Recency decay — fresh news matters
# ──────────────────────────────────────────────────────────────────

def _recency_score(published_at: datetime, half_life_hours: float = 18.0) -> float:
    """
    Exponential decay: an article's "freshness" halves every 18h.

    At t=0:   score = 1.0  (just published)
    At t=18h: score = 0.5
    At t=36h: score = 0.25

    Why exponential and not linear? News has a viral half-life. A 12h-old
    story is much "less hot" than a 1h-old one, but a 48h vs 60h difference
    barely matters. Exponential captures that natural decay curve.
    """
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - published_at).total_seconds() / 3600
    age_hours = max(age_hours, 0.0)
    return math.exp(-age_hours * math.log(2) / half_life_hours)


# ──────────────────────────────────────────────────────────────────
#  Public ranker
# ──────────────────────────────────────────────────────────────────

def rank_articles(
    articles: list[Any],          # SQLAlchemy TrendingArticle rows
    persona: dict[str, Any],
    top_k: int = 9,
    weights: tuple[float, float, float] = (0.5, 0.25, 0.25),
) -> list[Any]:
    """
    Rank articles for one user, return top K with scores attached.

    Adds two attributes to each returned article object:
        - relevance_score: BM25 vs persona vocabulary
        - final_score:     weighted combination

    Note: we mutate the rows in-memory only — these aren't persisted.
    """
    if not articles:
        return []

    α, β, γ = weights

    # Build the persona "query" set
    p_terms = _persona_terms(persona)

    # Tokenize all articles once — used for corpus stats and per-doc scoring
    tokenized: list[list[str]] = [
        _tokenize(f"{a.title} {a.description or ''}")
        for a in articles
    ]

    # Corpus statistics needed for BM25
    avg_len = sum(len(d) for d in tokenized) / len(tokenized) if tokenized else 1.0
    doc_freqs: Counter[str] = Counter()
    for doc_terms in tokenized:
        doc_freqs.update(set(doc_terms))

    scored: list[tuple[float, Any]] = []

    for article, doc_terms in zip(articles, tokenized, strict=True):
        relevance = _bm25(p_terms, doc_terms, avg_len, len(articles), doc_freqs)
        # Normalize BM25 (which is unbounded) into roughly 0-1 range
        relevance_norm = relevance / (relevance + 3.0)

        recency = _recency_score(article.published_at)

        final = α * relevance_norm + β * article.velocity_score + γ * recency

        # Attach scores for the response — these will surface in the API
        article.relevance_score = round(relevance_norm, 4)
        article.final_score = round(final, 4)

        scored.append((final, article))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in scored[:top_k]]