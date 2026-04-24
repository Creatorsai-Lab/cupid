"""
Quality Scorer — multi-axis evaluation of composed variants.

Every variant is scored on 4 axes, each 0.0 - 1.0:
    1. LENGTH_FIT      — within platform min/max, close to target
    2. GROUNDING       — references distilled facts (not hallucinated)
    3. PERSONA_MATCH   — vocabulary overlap with user's bio/USP
    4. HOOK_STRENGTH   — first-line quality heuristics

Composite score = weighted average. Below-threshold variants are flagged.

No LLM calls — all deterministic. This runs in ~1ms per variant, so
it's cheap to score even 10+ variants.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.agents.composer.platform_rules import PlatformRule


@dataclass
class QualityScore:
    length_fit: float
    grounding: float
    persona_match: float
    hook_strength: float
    composite: float
    passes_threshold: bool


# Weights for composite — grounding matters most (factual integrity)
_WEIGHTS = {
    "length_fit":    0.20,
    "grounding":     0.35,
    "persona_match": 0.20,
    "hook_strength": 0.25,
}

_MIN_COMPOSITE = 0.45  # below this, variant is flagged as low quality

_NUMBER_RE = re.compile(r"\b\d[\d.,%]*\b")

_WEAK_OPENERS = frozenset({
    "in", "as", "today", "nowadays", "in today's", "let's", "so,", "well,",
    "first", "firstly", "have", "did", "are", "here's", "heres",
})

_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "i", "you", "we", "they", "it", "of", "in", "on",
    "at", "for", "with", "by", "from", "about", "as", "to", "this",
    "that", "these", "those", "what", "which", "who", "when", "where",
})


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z\-]+", text.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 2}


def _score_length(content: str, rule: PlatformRule) -> float:
    """1.0 at target, 0.0 below min or above max, linear between."""
    length = len(content)
    if length < rule.min_chars or length > rule.max_chars:
        return 0.0
    target = rule.target_chars
    # Distance from target, normalized by the closer of the two bounds
    if length <= target:
        bound_dist = target - rule.min_chars
        return 1.0 - (target - length) / max(bound_dist, 1)
    else:
        bound_dist = rule.max_chars - target
        return 1.0 - (length - target) / max(bound_dist, 1)


def _score_grounding(
    content: str,
    facts: list[dict[str, Any]],
) -> float:
    """
    Does the post actually reference the distilled evidence?

    We check for:
    - Numbers appearing in facts also appearing in the post
    - Keyword overlap with fact text (strong signal)
    - Any number at all in the post (weaker signal — still shows specificity)
    """
    if not facts:
        # If no facts, don't penalize — upstream failure
        return 0.7

    content_tokens = _tokenize(content)
    content_numbers = set(_NUMBER_RE.findall(content))

    fact_numbers: set[str] = set()
    fact_tokens: set[str] = set()
    for f in facts:
        fact_text = f.get("fact", "")
        fact_numbers.update(_NUMBER_RE.findall(fact_text))
        fact_tokens.update(_tokenize(fact_text))

    # Number match is the strongest grounding signal
    number_overlap = len(content_numbers & fact_numbers) / max(len(fact_numbers), 1)
    # Keyword overlap
    keyword_overlap = len(content_tokens & fact_tokens) / max(len(fact_tokens), 1)
    # Has any number at all
    has_any_number = 1.0 if content_numbers else 0.0

    score = 0.5 * number_overlap + 0.3 * keyword_overlap + 0.2 * has_any_number
    return min(score, 1.0)


def _score_persona_match(
    content: str,
    personalization: dict[str, Any],
) -> float:
    """Lexical overlap between post and the persona's vocabulary."""
    persona_text = " ".join(
        str(personalization.get(k, ""))
        for k in ("bio", "usp", "content_niche", "target_audience")
    ).strip()
    if not persona_text:
        return 0.7  # neutral when no persona data

    content_tokens = _tokenize(content)
    persona_tokens = _tokenize(persona_text)
    if not persona_tokens:
        return 0.7

    overlap = len(content_tokens & persona_tokens)
    # Saturating curve — 3 shared terms is already great on short posts
    return min(overlap / 3.0, 1.0)


def _score_hook_strength(content: str) -> float:
    """
    Heuristics for first-line quality:
    - Specific (has number or named entity) → +
    - Short (under 12 words) → +
    - Weak opener → -
    - Question mark in first line → + (curiosity)
    """
    first_line = content.strip().split("\n", 1)[0].strip()
    if not first_line:
        return 0.0

    score = 0.5  # baseline

    first_words = first_line.lower().split()
    if not first_words:
        return 0.0

    # Weak opener penalty — check first 1-2 words
    first_two = " ".join(first_words[:2])
    if first_words[0] in _WEAK_OPENERS or first_two in _WEAK_OPENERS:
        score -= 0.25

    # Specificity bonus
    if _NUMBER_RE.search(first_line):
        score += 0.20
    # Capitalized proper nouns (not just sentence-start)
    proper_nouns = sum(
        1 for w in first_line.split()[1:] if w and w[0].isupper() and len(w) > 2
    )
    if proper_nouns >= 1:
        score += 0.15

    # Punchiness bonus — short first line
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
    length_fit    = _score_length(content, rule)
    grounding     = _score_grounding(content, facts)
    persona_match = _score_persona_match(content, personalization)
    hook_strength = _score_hook_strength(content)

    composite = (
        _WEIGHTS["length_fit"]    * length_fit
        + _WEIGHTS["grounding"]     * grounding
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