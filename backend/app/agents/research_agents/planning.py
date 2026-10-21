"""Planning and validation helpers for the research pipeline."""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from datetime import datetime
from typing import Any

from app.agents.research_agents.models import (
    FreshnessMode,
    PersonaContext,
    PlannedQuery,
    ResearchBrief,
    ResearchPlan,
)

_REQUEST_FILLER = frozenset(
    {
        "a",
        "an",
        "and",
        "all",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "find",
        "for",
        "from",
        "give",
        "i",
        "explain",
        "in",
        "is",
        "it",
        "me",
        "my",
        "need",
        "of",
        "on",
        "only",
        "or",
        "please",
        "show",
        "suggest",
        "the",
        "to",
        "under",
        "research",
        "using",
        "want",
        "we",
        "with",
    }
)
# Conversational scaffolding that never names a research subject. Removed from request
# anchors so "there is a my show next week so I am preparing" cannot sink a good plan.
_CONVERSATIONAL_REQUEST_WORDS = frozenset(
    {
        # Time words such as "today" or "this week" are deliberately kept: they can be a
        # user constraint the brief must preserve. Only durations used as scheduling chatter
        # ("next week", "this month") are dropped.
        "also",
        "am",
        "any",
        "before",
        "after",
        "few",
        "have",
        "has",
        "had",
        "help",
        "helping",
        "into",
        "just",
        "later",
        "looking",
        "lot",
        "lots",
        "many",
        "much",
        "next",
        "out",
        "over",
        "prepare",
        "prepared",
        "preparing",
        "really",
        "reference",
        "references",
        "refer",
        "so",
        "some",
        "something",
        "take",
        "taking",
        "than",
        "then",
        "there",
        "these",
        "thing",
        "things",
        "this",
        "those",
        "use",
        "used",
        "using",
        "very",
        "week",
        "weeks",
        "month",
        "months",
        "year",
        "years",
        "will",
        "would",
        "could",
        "should",
        "them",
        "they",
        "their",
        "our",
        "your",
        "you",
        "one",
        "ones",
        "which",
        "when",
        "what",
        "how",
        "why",
        "where",
        "who",
    }
)
_REQUEST_FRAMING_MAKE = re.compile(
    r"\b(?:can|could|may|might|should|would)\s+make\b", re.IGNORECASE
)
# "for example I made a video on ..." illustrates what the user already does; the brief need
# not repeat the example, so its words are not anchors. Bounded to the sentence it opens.
_EXAMPLE_CLAUSE = re.compile(
    r"\b(?:for\s+example|for\s+instance|e\.g\.)[^.!?\n]*", re.IGNORECASE
)
# "I'm a news podcaster" introduces the user, who reaches the planner as persona context anyway.
# Only "I'm/I am a/an ... <role>" is dropped, so "I'm a beginner looking for Rust tutorials" keeps its subject.
_SELF_INTRODUCTION = re.compile(
    r"\bI(?:'m|’m|\s+am)\s+an?\s+(?:[\w-]+\s+){0,5}?(?:analyst|blogger|creator|designer|developer|engineer|"
    r"founder|influencer|journalist|marketer|podcaster|researcher|student|teacher|writer|youtuber)s?\b",
    re.IGNORECASE,
)
# Words that name something specific: a capitalised word inside a sentence (India), an acronym
# (ML, AI) or a year (2026). A brief may never drop one, whatever the tolerance for plain words.
_NAMED_TERM = re.compile(
    r"(?<![.!?]\s)(?<!^)\b[A-Z][\w-]*|\b[A-Z]{2,}\b|\b(?:19|20)\d{2}\b"
)
# The user's own making and publishing workflow: in a content-delivery request these words say
# how the user works, not what to research.
_CONTENT_WORKFLOW_TERMS = frozenset(
    {
        "creator",
        "execute",
        "follower",
        "post",
        "posting",
        "publish",
        "publishing",
        "record",
        "share",
        "shoot",
        "upload",
    }
)
# The form the user wants material in ("system design guide and tips"), not what it is about:
# a brief saying "system design best practices" has kept the subject.
_CONTENT_FORM_TERMS = frozenset(
    {"advice", "example", "guide", "idea", "overview", "tip", "tips", "tutorial"}
)
_REQUEST_CONTEXT_NOISE = frozenset(
    {
        "about",
        "engagement",
        "get",
        "going",
        "like",
        "more",
        "news",
        "platform",
        "researcher",
        "social",
        "specially",
        "stuff",
        "stuffs",
        "user",
        "users",
    }
)
_PERSONA_FILLER = _REQUEST_FILLER | frozenset(
    {"content", "creator", "expert", "specialist", "strategist", "influencer"}
)
_KNOWN_PLATFORM_OR_AUDIENCE_TERMS = frozenset(
    {
        "instagram",
        "tiktok",
        "youtube",
        "facebook",
        "twitter",
        "twitch",
        "linkedin",
        "pinterest",
        "snapchat",
        "reddit",
        "discord",
        "quora",
        "medium",
        "substack",
        "threads",
        "x",
        "reels",
        "shorts",
        "millennial",
        "millennials",
        "gen",
        "zoomers",
        "boomer",
        "boomers",
        "parents",
        "teens",
    }
)
_DELIVERY_CONTEXT_TERMS = frozenset(
    {
        "audience",
        "creator",
        "format",
        "listener",
        "presentation",
        "reader",
        "tutorial",
        "video",
        "viewer",
    }
)
_HARD_RESEARCH_TERMS = frozenset(
    {
        "data",
        "official",
        "primary",
        "research",
        "source",
        "sources",
        "statistics",
        "study",
        "studies",
    }
)
_ANGLE_EQUIVALENCE_ROOTS = {
    "appeal": "visual",
    "appealing": "visual",
    "culture": "culture",
    "cultural": "culture",
    "diet": "dietary",
    "dietary": "dietary",
    "friendly": "suitability",
    "meaning": "culture",
    "narration": "culture",
    "preparation": "preparation",
    "prepare": "preparation",
    "prepared": "preparation",
    "preparing": "preparation",
    "presentation": "visual",
    "recipe": "preparation",
    "recipes": "preparation",
    "significance": "culture",
    "storytelling": "culture",
    "suitability": "suitability",
    "suitable": "suitability",
    "vegan": "dietary",
    "vegetarian": "dietary",
    "visual": "visual",
    "visually": "visual",
}
_GENERIC_ANGLE_ROOTS = frozenset(
    {
        "analysis",
        "context",
        "data",
        "guide",
        "information",
        "overview",
        "report",
        "research",
        "trend",
        "case studies",
        "entertainment",
    }
)
_GENERIC_PATH_SEGMENTS = frozenset(
    {
        "about",
        "archive",
        "article",
        "articles",
        "blog",
        "category",
        "home",
        "news",
        "post",
        "posts",
        "section",
        "story",
        "tag",
        "topics",
    }
)
_CURRENCY_CODES = {"$": "usd", "€": "eur", "£": "gbp", "₹": "inr", "¥": "jpy"}
_KNOWN_SHORT_DOMAIN_OR_GEOGRAPHY_TERMS = frozenset({"ai", "uk"})
_ACRONYM_SUBJECTS = {
    "ml": frozenset({"machine", "learning"}),
    "rl": frozenset({"reinforcement", "learning"}),
}
_DEFAULT_FRESHNESS_WINDOWS = {
    FreshnessMode.BREAKING: 10,
    FreshnessMode.RECENT: 90,
    FreshnessMode.CURRENT_CYCLE: 366,
}


class _PlanValidationError(ValueError):
    """Carry a schema-valid plan when a deterministic quality gate rejects it."""

    def __init__(self, message: str, plan: ResearchPlan) -> None:
        super().__init__(message)
        self.plan = plan


def _meaningful_tokens(
    text: str, *, filler: frozenset[str] = _REQUEST_FILLER
) -> set[str]:
    """Normalize terms worth preserving without treating request grammar as intent."""
    tokens = set()
    for token in re.findall(r"[\w$]+", text):
        normalized = token.casefold().strip("$")
        if not normalized or normalized in filler:
            continue
        is_uppercase_acronym = (
            token.isalpha() and token.isupper() and 2 <= len(token) <= 5
        )
        if (
            normalized.isdigit()
            or len(normalized) >= 3
            or normalized in _KNOWN_PLATFORM_OR_AUDIENCE_TERMS
            or normalized in _KNOWN_SHORT_DOMAIN_OR_GEOGRAPHY_TERMS
            or is_uppercase_acronym
        ):
            tokens.add(
                normalized
                if normalized in _KNOWN_PLATFORM_OR_AUDIENCE_TERMS
                else normalized.rstrip("s")
                if len(normalized) > 4
                else normalized
            )
    return tokens


def _preservation_tokens(text: str) -> set[str]:
    """Add deterministic amount-relation anchors to meaningful text tokens."""
    tokens = _meaningful_tokens(text)
    normalized = text.casefold()
    for relation, symbol, amount in re.findall(
        r"\b(under|below|less\s+than|at\s+most|maximum|max|over|above|more\s+than|at\s+least|minimum|min)\s*([$€£₹¥])?\s*(\d+(?:\.\d+)?)",
        normalized,
    ):
        direction = (
            "max"
            if relation in {"under", "below", "less than", "at most", "maximum", "max"}
            else "min"
        )
        tokens.add(f"{direction}_amount:{amount}")
        if symbol:
            currency = _CURRENCY_CODES[symbol]
            tokens.add(f"currency:{currency}")
            tokens.add(f"{direction}_amount:{currency}:{amount}")
    return tokens


def _request_preservation_tokens(text: str) -> set[str]:
    """Return hard research anchors without conversational or publishing context."""
    normalized = unicodedata.normalize("NFKC", text)
    tokens = (
        _preservation_tokens(_REQUEST_FRAMING_MAKE.sub("", normalized))
        - _REQUEST_CONTEXT_NOISE
        - _CONVERSATIONAL_REQUEST_WORDS
    )
    if _DELIVERY_SIGNAL.search(normalized):
        tokens -= _KNOWN_PLATFORM_OR_AUDIENCE_TERMS
    return tokens


def _request_anchor_tokens(text: str) -> set[str]:
    """Return the request subjects a brief must keep: no self-introduction, examples, content
    forms or delivery workflow.

    Grounding keeps the wider :func:`_request_preservation_tokens`, because a keyword the
    user names only inside an example is still the user's own word.
    """
    normalized = unicodedata.normalize("NFKC", text)
    subject = _EXAMPLE_CLAUSE.sub(" ", _SELF_INTRODUCTION.sub(" ", normalized))
    tokens = _request_preservation_tokens(subject) - _CONTENT_FORM_TERMS
    if _DELIVERY_SIGNAL.search(subject):
        tokens -= _CONTENT_WORKFLOW_TERMS
    return tokens


def _request_named_anchors(text: str) -> set[str]:
    """Return the request anchors that name something specific (India, ML, 2026) or an amount.

    These may never be dropped by a brief; only plain words share the missing-anchor tolerance.
    Taking them from :func:`_request_anchor_tokens` keeps its exclusions, so a capitalised
    platform in a posting request ("share on LinkedIn") is still not an anchor.
    """
    names = _meaningful_tokens(
        " ".join(_NAMED_TERM.findall(unicodedata.normalize("NFKC", text)))
    )
    return {
        anchor
        for anchor in _request_anchor_tokens(text)
        if anchor in names or ":" in anchor
    }


def _anchor_is_present(anchor: str, brief_terms: set[str]) -> bool:
    """Match a request anchor against brief terms tolerating typos, inflection and spelling.

    Exact matches and amount/currency anchors compare literally. Ordinary words of five or
    more letters also match a brief term that is close by edit similarity (comedie /
    comedy, humour / humor, refernence / reference). Underscored identifiers never match
    fuzzily, so injected markup such as ``user_request`` cannot pass as ``user_goal``.
    """
    if anchor in brief_terms:
        return True
    if ":" in anchor or "_" in anchor or anchor.isdigit() or len(anchor) < 5:
        return False
    candidates = [term for term in brief_terms if len(term) >= 5 and "_" not in term]
    # 0.75 admits one-letter inflection on six-letter words (comedie / comedy = 0.77) while
    # still rejecting unrelated words; underscored identifiers are excluded above.
    return bool(difflib.get_close_matches(anchor, candidates, n=1, cutoff=0.75))


def _semantic_tokens(text: str) -> set[str]:
    """Normalize Unicode and preservation anchors for intent-coverage comparisons."""
    return _preservation_tokens(unicodedata.normalize("NFKC", text))


def _with_acronym_equivalents(terms: set[str]) -> set[str]:
    """Return terms plus each acronym's spelled-out words and each spelled-out subject's acronym.

    A brief or query saying "machine learning" covers a request for "ML", and vice versa.
    """
    expanded = set(terms)
    for acronym, words in _ACRONYM_SUBJECTS.items():
        if acronym in terms:
            expanded |= words
        elif words <= terms:
            expanded.add(acronym)
    return expanded


def _angle_lexical_root(token: str) -> str:
    """Return a conservative comparison root for ordinary angle wording."""
    if token in _GENERIC_ANGLE_ROOTS:
        return token
    if token in _ANGLE_EQUIVALENCE_ROOTS:
        return _ANGLE_EQUIVALENCE_ROOTS[token]
    if token.startswith("prepar"):
        return "preparation"
    if token in {"ease", "easy", "easier", "easiest", "easiness"}:
        return "eas"
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith(("ches", "shes", "sses", "xes", "zes")) and len(token) > 5:
        return token[:-2]
    if token.endswith("ly") and len(token) > 5:
        return token[:-2]
    if token.endswith("ing") and len(token) > 6:
        return token[:-3]
    if token.endswith("ed") and len(token) > 5:
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss") and len(token) > 4:
        return token[:-1]
    return token


def _angle_lexical_tokens(text: str) -> set[str]:
    """Tokenize angle text without the plural damage tolerated by preservation matching."""
    tokens = set()
    for token in re.findall(r"[\w$]+", unicodedata.normalize("NFKC", text)):
        normalized = token.casefold().strip("$")
        if not normalized or normalized in _REQUEST_FILLER:
            continue
        is_uppercase_acronym = (
            token.isalpha() and token.isupper() and 2 <= len(token) <= 5
        )
        if (
            normalized.isdigit()
            or len(normalized) >= 3
            or normalized in _KNOWN_PLATFORM_OR_AUDIENCE_TERMS
            or normalized in _KNOWN_SHORT_DOMAIN_OR_GEOGRAPHY_TERMS
            or is_uppercase_acronym
        ):
            tokens.add(_angle_lexical_root(normalized))
    return tokens


def _normalized_text(text: str) -> str:
    """Normalize Unicode and whitespace for stable structured-response identities."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


def _query_lane_targets_angle(query: PlannedQuery, angle: str) -> bool:
    """Require meaningful lexical evidence for an angle while tolerating normal inflection."""
    angle_tokens = _angle_lexical_tokens(angle)
    lane_tokens = _angle_lexical_tokens(f"{query.purpose} {query.query}")
    matched = len(angle_tokens & lane_tokens)
    if len(angle_tokens) <= 1:
        return matched == 1
    if len(angle_tokens) == 2:
        return any(
            token not in _GENERIC_ANGLE_ROOTS for token in angle_tokens & lane_tokens
        )
    return matched >= 2 and matched * 2 >= len(angle_tokens)


def _ground_plan_declarations(plan: ResearchPlan, user_input: str) -> ResearchPlan:
    """Return a copy with only planner declarations grounded in the request."""
    request_terms = _request_preservation_tokens(user_input)
    explicitly_requests_research = bool(
        re.search(
            r"\bresearch\b", unicodedata.normalize("NFKC", user_input), re.IGNORECASE
        )
    )

    def grounded(values: tuple[str, ...]) -> tuple[str, ...]:
        retained = []
        for value in values:
            value_terms = _preservation_tokens(value)
            research_evidence = (
                value_terms == {"evidence"} and explicitly_requests_research
            )
            if value_terms and (
                value_terms.issubset(request_terms) or research_evidence
            ):
                retained.append(value)
        return tuple(retained)

    brief = plan.brief.model_copy(
        update={
            "main_keywords": grounded(plan.brief.main_keywords),
            "constraints": grounded(plan.brief.constraints),
        }
    )
    return plan.model_copy(update={"brief": brief})


def _is_soft_delivery_declaration(value: str) -> bool:
    """Identify grounded composition/delivery context rather than factual search scope."""
    terms = _meaningful_tokens(value)
    return bool(terms & _DELIVERY_CONTEXT_TERMS) and not bool(
        terms & _HARD_RESEARCH_TERMS
    )


def _hard_brief_declarations(brief: ResearchBrief) -> tuple[str, ...]:
    """Return grounded declarations that factual query text must preserve."""
    return tuple(
        value
        for value in (*brief.main_keywords, *brief.constraints)
        if not _is_soft_delivery_declaration(value)
    )


def _persona_values(persona: PersonaContext) -> tuple[str | None, ...]:
    """Return every profile value that must remain contextual rather than factual."""
    return (
        persona.bio,
        *persona.niches,
        persona.tone,
        persona.audience,
        persona.content_intent,
    )


def _sanitize_query_text(
    query_text: str,
    user_input: str,
    persona: PersonaContext,
) -> str:
    """Remove unrequested known/profile labels from one provider-facing query."""
    request_terms = _meaningful_tokens(user_input)
    persona_values = _persona_values(persona)
    persona_terms = set().union(
        *(
            _meaningful_tokens(value, filler=_PERSONA_FILLER)
            for value in persona_values
            if value
        )
    )
    blocked_terms = (persona_terms | _KNOWN_PLATFORM_OR_AUDIENCE_TERMS) - request_terms
    sanitized = unicodedata.normalize("NFKC", query_text)

    request_text = _normalized_text(user_input)
    persona_phrases = {
        "gen z",
        *(_normalized_text(value) for value in persona_values if value),
    }
    for phrase in sorted(persona_phrases, key=len, reverse=True):
        if not phrase or re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", request_text):
            continue
        sanitized = re.sub(
            rf"(?<!\w){re.escape(phrase)}(?!\w)", " ", sanitized, flags=re.IGNORECASE
        )

    for term in sorted(blocked_terms, key=len, reverse=True):
        sanitized = re.sub(
            rf"(?<!\w){re.escape(term)}(?!\w)", " ", sanitized, flags=re.IGNORECASE
        )
    return re.sub(r"\s+", " ", sanitized).strip(" \t\r\n,;:-")


def _persona_or_platform_leaks(
    query_terms: set[str],
    grounded_intent_terms: set[str],
    persona: PersonaContext,
) -> tuple[list[str], list[str]]:
    """Identify persona and known platform/audience labels absent from user research intent."""
    persona_terms = set().union(
        *(
            _meaningful_tokens(value, filler=_PERSONA_FILLER)
            for value in _persona_values(persona)
            if value
        )
    )
    leaked_persona = sorted((persona_terms & query_terms) - grounded_intent_terms)
    invented_labels = sorted(
        (_KNOWN_PLATFORM_OR_AUDIENCE_TERMS & query_terms) - grounded_intent_terms
    )
    return leaked_persona, invented_labels


def _required_freshness_window(brief: ResearchBrief) -> int | None:
    """Return the maximum acceptable query recency window for a time-sensitive brief."""
    if brief.freshness_mode == FreshnessMode.EVERGREEN:
        return None
    return (
        brief.freshness_window_days or _DEFAULT_FRESHNESS_WINDOWS[brief.freshness_mode]
    )


def _safe_prompt_data(value: Any) -> str:
    """Serialize untrusted prompt data so it cannot terminate a data block."""
    serialized = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return (
        serialized.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("`", "\\u0060")
    )


_FALLBACK_TOPIC_NOISE = _REQUEST_FILLER | frozenset(
    {
        "about",
        "am",
        "engagement",
        "get",
        "going",
        "like",
        "more",
        "platform",
        "researcher",
        "social",
        "specially",
        "stuff",
        "stuffs",
        "user",
        "users",
    }
)
_DELIVERY_SIGNAL = re.compile(
    r"\b(?:content|engagement|followers?|post(?:ing)?|publish(?:ing)?|share|social\s+platform)\b",
    re.IGNORECASE,
)


def _fallback_topic(user_input: str) -> str:
    """Extract a compact search subject without depending on another model call."""
    normalized = unicodedata.normalize("NFKC", user_input).strip()
    normalized = re.sub(
        r"\bpost[\s-]+training\b", "post-training", normalized, flags=re.IGNORECASE
    )
    delivery_context = bool(_DELIVERY_SIGNAL.search(normalized))
    seen: set[str] = set()
    retained: list[str] = []
    for token in re.findall(r"[\w+#]+(?:-[\w+#]+)*", normalized):
        folded = token.casefold()
        if folded in _FALLBACK_TOPIC_NOISE:
            continue
        if delivery_context and folded in _KNOWN_PLATFORM_OR_AUDIENCE_TERMS:
            continue
        if folded == "post" and delivery_context:
            continue
        if folded in seen:
            continue
        seen.add(folded)
        retained.append(token)
        if len(retained) == 12:
            break
    topic = " ".join(retained).strip()
    return topic[:180] or normalized[:180] or "current topic"


def _without_delivery_platforms(text: str, user_input: str) -> str:
    """Remove social destinations when the request frames them as publishing context."""
    if not _DELIVERY_SIGNAL.search(unicodedata.normalize("NFKC", user_input)):
        return text.strip()
    cleaned = unicodedata.normalize("NFKC", text)
    for platform in sorted(_KNOWN_PLATFORM_OR_AUDIENCE_TERMS, key=len, reverse=True):
        cleaned = re.sub(
            rf"(?<!\w){re.escape(platform)}(?!\w)", " ", cleaned, flags=re.IGNORECASE
        )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" \t\r\n,;:-")
    cleaned = re.sub(
        r"(?:\s+\b(?:and|for|on|via)\b)+\s*$", "", cleaned, flags=re.IGNORECASE
    )
    return cleaned.strip(" \t\r\n,;:-")


def _planning_failure_summary(kind: str, error: BaseException) -> str:
    """Return a bounded diagnostic suitable for persisted JSON."""
    message = re.sub(r"\s+", " ", str(error)).strip()
    return f"{kind}: {type(error).__name__}: {message}"[:400]


def _lane_query(topic: str, angle: str) -> str:
    """Append only the angle words the topic lacks.

    Repeating topic words ("... social work channels community impact and social work video
    concepts") over-weights them and drags search results off the subject.
    """
    topic_terms = _meaningful_tokens(topic)
    return " ".join(
        (
            topic,
            *(word for word in angle.split() if _meaningful_tokens(word) - topic_terms),
        )
    )


def _fallback_research_plan(
    user_input: str,
    now: datetime,
    *,
    seed: ResearchPlan | None = None,
) -> ResearchPlan:
    """Build three purposeful query lanes locally, reusing a valid model brief when possible."""
    normalized_request = unicodedata.normalize("NFKC", user_input)
    if seed is not None:
        cleaned_topic = _without_delivery_platforms(seed.brief.topic, user_input)
        cleaned_goal = _without_delivery_platforms(seed.brief.user_goal, user_input)
        brief = seed.brief.model_copy(
            update={
                "topic": cleaned_topic or _fallback_topic(user_input),
                "user_goal": cleaned_goal
                or f"Research reliable information about {_fallback_topic(user_input)}",
            }
        )
        topic = brief.topic.strip() or _fallback_topic(user_input)
        supplied_angles = brief.required_angles
        freshness_mode = brief.freshness_mode
        freshness_window_days = brief.freshness_window_days
    else:
        topic = _fallback_topic(user_input)
        time_sensitive = bool(
            re.search(
                r"\b(?:breaking|current|latest|new|news|recent|today|this\s+(?:week|month|year))\b",
                normalized_request,
                re.IGNORECASE,
            )
        )
        freshness_mode = (
            FreshnessMode.RECENT if time_sensitive else FreshnessMode.EVERGREEN
        )
        freshness_window_days = 90 if time_sensitive else None
        supplied_angles = ()
        brief = ResearchBrief(
            topic=topic,
            user_goal=f"Research reliable, relevant information about {topic}",
            required_angles=(
                "latest developments",
                "primary-source evidence",
                "expert analysis and implications",
            )
            if time_sensitive
            else (
                "key facts and context",
                "primary-source evidence",
                "practical implications",
            ),
            freshness_mode=freshness_mode,
            freshness_window_days=freshness_window_days,
            search_query_count=3,
        )

    angles: list[str] = []
    seen_angles: set[str] = set()
    generic_angles = (
        (
            "latest developments",
            "primary-source evidence",
            "expert analysis and implications",
        )
        if freshness_mode != FreshnessMode.EVERGREEN
        else ("practical examples", "how-to guidance", "expert tips")
    )
    for angle in (*supplied_angles, *generic_angles):
        normalized_angle = _normalized_text(angle)
        if normalized_angle and normalized_angle not in seen_angles:
            seen_angles.add(normalized_angle)
            angles.append(angle.strip())
        if len(angles) == 5:
            break
    while len(angles) < 3:
        angle = ("key facts", "reliable sources", "practical implications")[len(angles)]
        if _normalized_text(angle) not in seen_angles:
            seen_angles.add(_normalized_text(angle))
            angles.append(angle)

    query_count = min(5, max(3, len(supplied_angles) if supplied_angles else 3))
    angles = angles[:query_count]
    time_sensitive_plan = freshness_mode != FreshnessMode.EVERGREEN
    year_suffix = f" {now.year}" if time_sensitive_plan else ""
    if time_sensitive_plan:
        source_types = (
            "primary research",
            "official sources",
            "case studies",
            "news analysis",
            "data report",
        )
        intents = ("news", "fact", "analysis", "news", "data")
    else:
        # An evergreen request wants material and guidance, not headlines: a "news" intent
        # switches the search provider to its news index and returns reportage *about* the
        # topic instead of pages *of* it (e.g. articles about comedians instead of jokes).
        source_types = (
            "guides and tutorials",
            "examples and collections",
            "expert advice",
            "in-depth analysis",
            "reference",
        )
        intents = ("how_to", "examples", "guide", "analysis", "fact")
    queries = tuple(
        PlannedQuery(
            id=f"fallback-{index + 1}",
            query=re.sub(
                r"\s+", " ", f"{_lane_query(topic, angle)}{year_suffix}"
            ).strip()[:300],
            purpose=angle,
            intent=intents[index],
            freshness_window_days=freshness_window_days,
            preferred_source_type=source_types[index],
        )
        for index, angle in enumerate(angles)
    )
    repaired_brief = brief.model_copy(update={"search_query_count": len(queries)})
    # The seed's backups answer the same brief angles; each is validated again before use.
    backups = seed.backup_queries if seed is not None else ()
    return ResearchPlan(brief=repaired_brief, queries=queries, backup_queries=backups)


def _gap_query(
    brief: ResearchBrief,
    angle: str,
    text: str,
    identifier: str,
    attempted_queries: tuple[PlannedQuery, ...],
) -> PlannedQuery:
    """Build the one recovery lane for ``angle`` under an ID no attempted lane uses."""
    existing_ids = {_normalized_text(query.id) for query in attempted_queries}
    candidate = identifier
    suffix = 2
    while _normalized_text(candidate) in existing_ids:
        candidate = f"{identifier}-{suffix}"
        suffix += 1
    return PlannedQuery(
        id=candidate,
        query=re.sub(r"\s+", " ", text).strip()[:300],
        purpose=angle,
        intent="news" if brief.freshness_mode != FreshnessMode.EVERGREEN else "fact",
        freshness_window_days=_required_freshness_window(brief),
        preferred_source_type="primary or authoritative source",
    )


def _fallback_gap_query(
    brief: ResearchBrief,
    missing_angles: tuple[str, ...],
    attempted_queries: tuple[PlannedQuery, ...],
) -> PlannedQuery:
    """Build one safe recovery lane from the brief alone, for when no planner backup is usable."""
    angle = missing_angles[0] if missing_angles else "additional reliable evidence"
    parts = [brief.topic, angle]
    current_terms = _semantic_tokens(" ".join(parts))
    for declaration in _hard_brief_declarations(brief):
        declaration_terms = _semantic_tokens(declaration)
        if declaration_terms and not declaration_terms.issubset(current_terms):
            parts.append(declaration)
            current_terms.update(declaration_terms)
    return _gap_query(brief, angle, " ".join(parts), "gap-fallback", attempted_queries)
