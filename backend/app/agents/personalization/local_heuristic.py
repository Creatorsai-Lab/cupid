"""
Local Heuristic Query Generator.

Zero-LLM, deterministic query decomposition that produces personalized,
angle-diversified search queries using structured NLP heuristics.

Approach:
    1. Extract the core entity/topic from the user prompt (noun phrase chunking)
    2. Derive persona-aware modifiers from creator context
    3. Template-fill 5 angle-specific query patterns
    4. Rank and dedupe against each other

Never raises — even on empty input it returns usable queries.

No external dependencies beyond the standard library.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

# ─── Static lexicons ─────────────────────────────────────────────

# Words too generic to be the "topic" of a query
_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "this", "that", "these", "those", "and", "or", "but",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "should", "could", "may", "might",
    "can", "i", "you", "we", "they", "it", "he", "she", "what", "which",
    "who", "when", "where", "why", "how", "to", "of", "in", "on", "at",
    "for", "with", "by", "from", "about", "as", "into", "through", "want",
    "need", "like", "know", "tell", "show", "make", "create", "write",
    "post", "content", "tweet", "thread",
})

# Filler modifiers — not useful as query terms
_FILLER: frozenset[str] = frozenset({
    "really", "very", "quite", "just", "simply", "basically", "actually",
    "literally", "something", "anything", "everything", "stuff", "things",
    "good", "bad", "nice", "great", "cool", "awesome",
})

# Niche-specific vocabulary boosters — added to queries when topic matches
_NICHE_BOOSTERS: dict[str, dict[str, list[str]]] = {
    "ai/ml": {
        "facts":      ["benchmark", "paper", "arxiv"],
        "recency":    ["2025", "latest release"],
        "expertise":  ["research", "ablation study"],
        "practical":  ["implementation", "github", "tutorial"],
        "contrarian": ["limitations", "failure modes"],
    },
    "software": {
        "facts":      ["documentation", "specification"],
        "recency":    ["2025", "release notes"],
        "expertise":  ["architecture", "best practices"],
        "practical":  ["tutorial", "example", "github"],
        "contrarian": ["anti-pattern", "pitfalls"],
    },
    "fitness": {
        "facts":      ["study", "meta-analysis", "research"],
        "recency":    ["2025 guidelines"],
        "expertise":  ["coach", "expert recommendation"],
        "practical":  ["routine", "program", "how to"],
        "contrarian": ["myths", "common mistakes"],
    },
    "finance": {
        "facts":      ["data", "report", "statistics"],
        "recency":    ["2025 market", "this quarter"],
        "expertise":  ["analyst", "outlook"],
        "practical":  ["strategy", "step by step"],
        "contrarian": ["risks", "bear case"],
    },
    "marketing": {
        "facts":      ["case study", "benchmark"],
        "recency":    ["2025 trends"],
        "expertise":  ["framework", "playbook"],
        "practical":  ["template", "example"],
        "contrarian": ["what doesn't work"],
    },
    "health": {
        "facts":      ["clinical study", "research"],
        "recency":    ["2025 guidelines"],
        "expertise":  ["doctor", "specialist"],
        "practical":  ["how to", "guide"],
        "contrarian": ["side effects", "myths"],
    },
    "creator": {
        "facts":      ["case study", "analytics"],
        "recency":    ["2025 algorithm"],
        "expertise":  ["creator interview", "breakdown"],
        "practical":  ["template", "workflow"],
        "contrarian": ["what failed"],
    },
}

# Default angle modifiers — used when no niche match
_DEFAULT_ANGLES: dict[str, list[str]] = {
    "facts":      ["statistics", "data"],
    "recency":    ["2025", "latest"],
    "expertise":  ["expert analysis", "research"],
    "practical":  ["guide", "how to"],
    "contrarian": ["criticism", "drawbacks"],
}

# Audience sophistication mapping — affects vocabulary complexity
_AUDIENCE_HINTS: dict[str, str] = {
    "developer":    "technical",
    "engineer":     "technical",
    "researcher":   "academic",
    "student":      "beginner",
    "founder":      "strategic",
    "entrepreneur": "strategic",
    "marketer":     "applied",
    "designer":     "applied",
}


# ─── Core extraction ─────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, preserve hyphenated terms."""
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9\-\+\.#]*", text.lower())


def _extract_topic(prompt: str) -> str:
    """
    Pull the core topic from a user prompt using noun-phrase-ish heuristics.

    Strategy:
    - Drop imperatives ("write a post about X" → "X")
    - Drop stopwords and fillers
    - Keep proper nouns (capitalized in original), numbers, acronyms
    - Preserve bigram entities (e.g. "vector database")
    """
    # Remove common imperatives
    cleaned = re.sub(
        r"^(write|create|make|generate|compose|give me|i want|help me with)\s+"
        r"(a |an |the )?(post|tweet|thread|content|article)?\s*(about|on|for)?\s*",
        "",
        prompt.strip(),
        flags=re.IGNORECASE,
    )

    tokens = _tokenize(cleaned)
    if not tokens:
        return prompt.strip() or "the topic"

    # Preserve original-case proper nouns before lowercasing
    original_tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-\+\.#]*", cleaned)
    proper_nouns = {
        tok.lower() for tok in original_tokens
        if tok[0].isupper() and tok.lower() not in _STOPWORDS
    }

    keep = [
        tok for tok in tokens
        if tok not in _STOPWORDS and tok not in _FILLER and len(tok) > 1
    ]

    # If we have proper nouns, they anchor the topic
    if proper_nouns:
        anchored = [tok for tok in keep if tok in proper_nouns]
        remaining = [tok for tok in keep if tok not in proper_nouns]
        keep = anchored + remaining

    if not keep:
        return cleaned.strip() or "the topic"

    # Cap to ~5 words so the topic stays crisp
    return " ".join(keep[:5])


# ─── Persona processing ──────────────────────────────────────────

def _resolve_niche_key(niche: str) -> str:
    """Map a user's niche string to our booster lexicon key."""
    n = niche.lower()
    if any(k in n for k in ("ai", "ml", "machine learning", "data scien")):
        return "ai/ml"
    if any(k in n for k in ("software", "web dev", "programming", "coding")):
        return "software"
    if any(k in n for k in ("fitness", "gym", "workout", "exercise")):
        return "fitness"
    if any(k in n for k in ("finance", "invest", "crypto", "stock", "money")):
        return "finance"
    if any(k in n for k in ("market", "growth", "seo", "ads")):
        return "marketing"
    if any(k in n for k in ("health", "wellness", "nutrition", "mental")):
        return "health"
    if any(k in n for k in ("creator", "content", "youtube", "podcast")):
        return "creator"
    return ""


def _audience_sophistication(audience: str) -> str:
    a = audience.lower()
    for keyword, level in _AUDIENCE_HINTS.items():
        if keyword in a:
            return level
    return ""


def _region_modifier(country: str) -> str:
    """Add regional specificity only when it meaningfully narrows results."""
    c = country.strip().lower()
    if not c or c in ("global", "worldwide", "all"):
        return ""
    # Multi-country → skip
    if "," in c or "/" in c:
        return ""
    return country.strip()


# ─── Query assembly ──────────────────────────────────────────────

def _assemble_query(topic: str, modifiers: list[str], region: str = "") -> str:
    """Build a single query from topic + angle modifiers + optional region."""
    parts = [topic]
    parts.extend(m for m in modifiers if m)
    if region:
        parts.append(region)

    # Cap at 9 words; strip duplicates while preserving order
    seen: set[str] = set()
    words: list[str] = []
    for part in parts:
        for word in part.split():
            w_lower = word.lower()
            if w_lower not in seen:
                seen.add(w_lower)
                words.append(word)
            if len(words) >= 9:
                break
        if len(words) >= 9:
            break

    return " ".join(words).strip()


def _select_boosters(niche_key: str, angle: str, sophistication: str) -> list[str]:
    """Pick the best 1-2 modifier terms for an angle, given niche + audience."""
    table = _NICHE_BOOSTERS.get(niche_key, _DEFAULT_ANGLES)
    candidates = table.get(angle, _DEFAULT_ANGLES[angle])

    # Audience sophistication filters vocabulary
    if sophistication == "academic" and angle == "expertise":
        return ["peer-reviewed", "study"]
    if sophistication == "beginner" and angle == "practical":
        return ["beginner guide", "step by step"]
    if sophistication == "technical" and angle == "practical":
        return ["implementation", "github"]
    if sophistication == "strategic" and angle == "contrarian":
        return ["risks", "tradeoffs"]

    return [candidates[0]]


# ─── Public API ──────────────────────────────────────────────────

def generate_queries(
    prompt: str,
    personalization: dict[str, Any] | None = None,
) -> list[str]:
    """
    Generate 5 angle-decomposed search queries with zero LLM calls.

    Angles (always in this order):
        1. FACTS      — statistics, benchmarks, definitions
        2. RECENCY    — latest developments, current year
        3. EXPERTISE  — expert analysis, research
        4. PRACTICAL  — how-to, tutorials, implementation
        5. CONTRARIAN — criticism, failures, edge cases

    Args:
        prompt: Raw user topic/intent string.
        personalization: Creator profile dict. Supported keys:
            - content_niche:   maps to niche-specific vocabulary
            - target_audience: affects query sophistication
            - target_country:  adds regional specificity
            - content_intent:  currently unused (reserved)
            - usp:             currently unused (reserved)

    Returns:
        Exactly 5 search query strings, each 3-9 words long.
    """
    persona = personalization or {}

    topic = _extract_topic(prompt)
    niche_key = _resolve_niche_key(str(persona.get("content_niche") or ""))
    sophistication = _audience_sophistication(str(persona.get("target_audience") or ""))
    region = _region_modifier(str(persona.get("target_country") or ""))

    # Replace "2025" in boosters with current year dynamically
    current_year = str(datetime.now().year)

    angles = ["facts", "recency", "expertise", "practical", "contrarian"]
    queries: list[str] = []

    for angle in angles:
        boosters = _select_boosters(niche_key, angle, sophistication)
        boosters = [b.replace("2025", current_year) for b in boosters]

        # Region applies only to recency and practical — most location-sensitive
        use_region = region if angle in ("recency", "practical") else ""

        query = _assemble_query(topic, boosters, use_region)
        queries.append(query)

    return _ensure_diversity(queries)


def _ensure_diversity(queries: list[str]) -> list[str]:
    """
    Last-mile dedup: if two queries collapse to the same normalized form,
    perturb the second one with a secondary modifier so they stay distinct.
    """
    seen: dict[str, int] = {}
    fallback_modifiers = ["overview", "breakdown", "explained", "analysis", "review"]

    out: list[str] = []
    for i, q in enumerate(queries):
        key = " ".join(sorted(q.lower().split()))
        if key in seen:
            mod = fallback_modifiers[i % len(fallback_modifiers)]
            q = f"{q} {mod}"
            key = " ".join(sorted(q.lower().split()))
        seen[key] = i
        out.append(q)

    return out