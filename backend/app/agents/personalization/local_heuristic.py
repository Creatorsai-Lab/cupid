"""
Local Heuristic Query Generator.

Zero-LLM, deterministic query decomposition inspired by how Perplexity
and Manus structure research lookups. Each angle uses a purpose-built
query template — never a mechanical "topic + modifier" concat.

The output reads like a human researcher's search history, not like
a bag of keywords.

No external dependencies beyond the standard library.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

# ─── Lexicons ────────────────────────────────────────────────────

_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "this", "that", "these", "those", "and", "or", "but",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "should", "could", "may", "might",
    "can", "i", "you", "we", "they", "it", "he", "she", "what", "which",
    "who", "when", "where", "why", "how", "to", "of", "in", "on", "at",
    "for", "with", "by", "from", "about", "as", "into", "through", "want",
    "need", "like", "know", "tell", "show", "write", "post", "content",
    "tweet", "thread", "article", "some", "also",
})

_FILLER: frozenset[str] = frozenset({
    "just", "really", "very", "simply", "basically", "actually", "literally",
    "something", "anything", "everything", "stuff", "things", "good", "bad",
    "great", "cool", "awesome", "nice",
})

# Niche-specific config drives angle templates
_NICHE_CONFIG: dict[str, dict[str, Any]] = {
    "ai/ml": {
        "expert_term":    "researchers",
        "practical_verb": "implement",
        "failure_term":   "limitations",
        "recency_term":   "SOTA",
    },
    "software": {
        "expert_term":    "senior engineers",
        "practical_verb": "build",
        "failure_term":   "pitfalls",
        "recency_term":   "best practices",
    },
    "fitness": {
        "expert_term":    "coaches",
        "practical_verb": "train",
        "failure_term":   "mistakes",
        "recency_term":   "guidelines",
    },
    "finance": {
        "expert_term":    "analysts",
        "practical_verb": "invest in",
        "failure_term":   "risks",
        "recency_term":   "forecast",
    },
    "marketing": {
        "expert_term":    "growth leads",
        "practical_verb": "run",
        "failure_term":   "what doesn't work",
        "recency_term":   "trends",
    },
    "health": {
        "expert_term":    "doctors",
        "practical_verb": "manage",
        "failure_term":   "side effects",
        "recency_term":   "guidelines",
    },
    "creator": {
        "expert_term":    "top creators",
        "practical_verb": "grow",
        "failure_term":   "mistakes to avoid",
        "recency_term":   "algorithm updates",
    },
}

_DEFAULT_CONFIG: dict[str, Any] = {
    "expert_term":    "experts",
    "practical_verb": "use",
    "failure_term":   "drawbacks",
    "recency_term":   "trends",
}

# Audience sophistication modulates phrasing
_AUDIENCE_HINTS: dict[str, str] = {
    "developer":    "technical",
    "engineer":     "technical",
    "researcher":   "academic",
    "academic":     "academic",
    "student":      "beginner",
    "beginner":     "beginner",
    "founder":      "strategic",
    "entrepreneur": "strategic",
    "ceo":          "strategic",
    "marketer":     "applied",
    "designer":     "applied",
}


# ─── Topic extraction ────────────────────────────────────────────

def _extract_topic(prompt: str) -> str:
    """
    Pull core topic by stripping imperatives and noise.

    "Write a post about RAG pipelines" -> "RAG pipelines"
    "Help me understand vector databases" -> "vector databases"
    """
    cleaned = re.sub(
        r"^(please\s+)?(write|create|make|generate|compose|give me|"
        r"i want|i need|help me (with|understand)|tell me about|explain)\s+"
        r"(a |an |the )?"
        r"(post|tweet|thread|article|content|piece|something)?\s*"
        r"(about|on|for|regarding)?\s*",
        "",
        prompt.strip(),
        flags=re.IGNORECASE,
    ).strip()

    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-\+\.#]*", cleaned)
    proper_nouns = {
        tok for tok in tokens
        if tok[0].isupper() and tok.lower() not in _STOPWORDS
    }

    keep: list[str] = []
    for tok in tokens:
        if tok in proper_nouns:
            keep.append(tok)
        elif (
            tok.lower() not in _STOPWORDS
            and tok.lower() not in _FILLER
            and len(tok) > 1
        ):
            keep.append(tok.lower())

    if not keep:
        return prompt.strip() or "the topic"

    return " ".join(keep[:5])


# ─── Persona mapping ─────────────────────────────────────────────

def _resolve_niche(niche: str) -> dict[str, Any]:
    n = niche.lower()
    if any(k in n for k in ("ai", "ml", "machine learning", "data scien", "llm")):
        return _NICHE_CONFIG["ai/ml"]
    if any(k in n for k in ("software", "web dev", "programming", "coding", "engineer")):
        return _NICHE_CONFIG["software"]
    if any(k in n for k in ("fitness", "gym", "workout", "exercise", "bodybuilding")):
        return _NICHE_CONFIG["fitness"]
    if any(k in n for k in ("finance", "invest", "crypto", "stock", "money", "trading")):
        return _NICHE_CONFIG["finance"]
    if any(k in n for k in ("market", "growth", "seo", "ads", "brand")):
        return _NICHE_CONFIG["marketing"]
    if any(k in n for k in ("health", "wellness", "nutrition", "mental", "medical")):
        return _NICHE_CONFIG["health"]
    if any(k in n for k in ("creator", "youtube", "podcast", "influencer")):
        return _NICHE_CONFIG["creator"]
    return _DEFAULT_CONFIG


def _audience_tier(audience: str) -> str:
    a = audience.lower()
    for keyword, tier in _AUDIENCE_HINTS.items():
        if keyword in a:
            return tier
    return "general"


def _region(country: str) -> str:
    c = country.strip().lower()
    if not c or c in ("global", "worldwide", "all") or "," in c:
        return ""
    return country.strip()


# ─── Per-angle query templates ───────────────────────────────────
#
# Each function builds one natural query phrased the way a researcher
# would actually type it into Google. No topic+junk concatenation.

def _q_facts(topic: str, cfg: dict[str, Any], tier: str) -> str:
    if tier == "academic":
        return f"{topic} empirical study results"
    if tier == "technical":
        return f"{topic} benchmark performance data"
    if tier == "beginner":
        return f"{topic} explained simply"
    if tier == "strategic":
        return f"{topic} market size statistics"
    return f"{topic} key statistics"


def _q_recency(topic: str, cfg: dict[str, Any], tier: str, year: str, region: str) -> str:
    term = cfg["recency_term"]
    parts = [topic, year, term]
    if region:
        parts.append(region)
    return " ".join(parts)


def _q_expertise(topic: str, cfg: dict[str, Any], tier: str) -> str:
    expert = cfg["expert_term"]
    if tier == "academic":
        return f"{topic} peer-reviewed research"
    if tier == "technical":
        return f"{topic} deep dive architecture"
    if tier == "strategic":
        return f"{topic} industry analysis report"
    return f"what {expert} say about {topic}"


def _q_practical(topic: str, cfg: dict[str, Any], tier: str, region: str) -> str:
    verb = cfg["practical_verb"]
    if tier == "beginner":
        base = f"how to {verb} {topic} step by step"
    elif tier == "technical":
        base = f"{topic} implementation example github"
    elif tier == "strategic":
        base = f"{topic} framework playbook"
    else:
        base = f"how to {verb} {topic}"

    if region and tier != "technical":
        base += f" {region}"
    return base


def _q_contrarian(topic: str, cfg: dict[str, Any], tier: str) -> str:
    failure = cfg["failure_term"]
    if tier == "academic":
        return f"{topic} methodological criticisms"
    if tier == "technical":
        return f"{topic} production failure modes"
    if tier == "strategic":
        return f"{topic} risks tradeoffs"
    if tier == "beginner":
        return f"common {topic} mistakes beginners make"
    return f"{topic} {failure}"


# ─── Public API ──────────────────────────────────────────────────

def generate_queries(
    prompt: str,
    personalization: dict[str, Any] | None = None,
) -> list[str]:
    """
    Generate 5 angle-decomposed queries using persona-aware templates.

    Angles (in order):
      1. FACTS      — statistics, definitions, data
      2. RECENCY    — current-year developments
      3. EXPERTISE  — what authorities say
      4. PRACTICAL  — how-to, implementation
      5. CONTRARIAN — criticism, failure modes

    Each query reads naturally and targets distinct search results.
    """
    persona = personalization or {}

    topic  = _extract_topic(prompt)
    cfg    = _resolve_niche(str(persona.get("content_niche") or ""))
    tier   = _audience_tier(str(persona.get("target_audience") or ""))
    region = _region(str(persona.get("target_country") or ""))
    year   = str(datetime.now().year)

    queries = [
        _q_facts(topic, cfg, tier),
        _q_recency(topic, cfg, tier, year, region),
        _q_expertise(topic, cfg, tier),
        _q_practical(topic, cfg, tier, region),
        _q_contrarian(topic, cfg, tier),
    ]

    return [_clamp(q) for q in queries]


def _clamp(query: str) -> str:
    """Clean whitespace, cap at 9 words, dedup consecutive tokens."""
    words = query.split()
    cleaned: list[str] = []
    prev = ""
    for w in words:
        if w.lower() != prev.lower():
            cleaned.append(w)
            prev = w
    return " ".join(cleaned[:9])