"""
app/earn/coach.py
═══════════════════════════════════════════════════════════════════════════

The ONLY place an LLM touches the Earn feature. It does NOT decide anything —
eligibility, tier, and matching are all settled deterministically before we
get here. The coach's job is pure expression:

  • Section 2 narrative — turn the computed ReadinessReport into a warm,
    specific coaching paragraph.
  • Section 4 creative ideas — niche-specific, concrete revenue ideas (the
    "food vlogger: feature brand products to get noticed" / "animator: pitch
    local shops" kind of suggestion). This is where an LLM genuinely shines
    and rules can't compete.

GROUNDED, NOT GENERATIVE-OF-FACTS
─────────────────────────────────
The prompt receives the conclusions as fixed facts and is explicitly forbidden
from inventing streams, contradicting eligibility, or promising earnings. Same
discipline as your evidence distiller: the model writes around the findings,
it never overrules them.

SELF-CONTAINED + GRACEFUL
─────────────────────────
Per the brief, this doesn't import your existing LLM provider chain. It calls
Groq directly (the provider you already use) reading GROQ_API_KEY from env. If
the key is missing or the call fails, it falls back to a deterministic
heuristic narrator so the page ALWAYS renders. The LLM is an enhancement, not
a dependency.
"""

from __future__ import annotations

import json
import logging

from app.earn.config import TIER_BLURB
from app.earn.readiness import ReadinessReport, StreamState
from app.earn.schemas import CreativeIdea

logger = logging.getLogger("app.earn.coach")

_GROQ_MODEL = "llama-3.3-70b-versatile"
_MAX_TOKENS = 700


# ─────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────


async def write_coaching(report: ReadinessReport, niche: str | None) -> str:
    """Section 2 narrative. Falls back to a heuristic summary on any failure."""
    findings = _findings_for_prompt(report, niche)
    prompt = _COACH_PROMPT.format(findings=json.dumps(findings, indent=2))
    text = await _try_groq(prompt, want_json=False)
    if text:
        return text.strip()
    return _heuristic_coaching(report)


async def write_creative_ideas(
    report: ReadinessReport, niche: str | None
) -> list[CreativeIdea]:
    """Section 4 ideas. Falls back to niche-agnostic templates on failure."""
    findings = _findings_for_prompt(report, niche)
    prompt = _IDEAS_PROMPT.format(
        niche=niche or "general content creation",
        findings=json.dumps(findings, indent=2),
    )
    raw = await _try_groq(prompt, want_json=True)
    if raw:
        ideas = _parse_ideas(raw)
        if ideas:
            return ideas
    return _heuristic_ideas(report, niche)


# ─────────────────────────────────────────────────────────────────────────
#  Prompt construction
# ─────────────────────────────────────────────────────────────────────────


def _findings_for_prompt(report: ReadinessReport, niche: str | None) -> dict:
    """Flatten the report into the minimal facts the model needs — nothing more."""
    return {
        "niche": niche or "unspecified",
        "tier": report.tier.value,
        "confidence": report.assessment.confidence,
        "engagement_note": report.assessment.flex_reason,
        "total_followers": report.assessment.signals.total_followers,
        "ready_now": [
            s.label for s in report.ranked_gaps if s.state == StreamState.GREEN_LIGHT
        ],
        "almost_ready": [
            s.label for s in report.ranked_gaps if s.state == StreamState.ALMOST_THERE
        ],
        "already_doing": [s.label for s in report.optimizing],
        "grow_toward": [s.label for s in report.foundation],
    }


_COACH_PROMPT = """You are a sharp, honest monetization coach for content creators.
Below are the COMPUTED findings about one creator. They are FACTS — do not contradict them.

{findings}

Write a warm, direct 2-3 sentence coaching summary that:
- Names where they stand (their tier) plainly and encouragingly.
- Highlights their single best next move from "ready_now" (or, if empty, from "almost_ready").
- If "engagement_note" is present, work that insight in — it's a genuine strength or caution.
- If confidence is "low", gently note the advice sharpens as they connect more accounts.

HARD RULES:
- NEVER promise or estimate any amount of money, income, or earnings.
- NEVER tell them to start something listed in "already_doing".
- NEVER invent a revenue stream not present in the findings.
- No bullet points, no headers. Plain, encouraging prose. Second person ("you")."""


_IDEAS_PROMPT = """You are a creative monetization coach. Generate concrete, niche-specific
revenue ideas for a {niche} creator, grounded in these computed findings:

{findings}

Produce 3 ideas. Each must be:
- SPECIFIC to the niche (not generic "post more"). E.g. for a food vlogger:
  "Feature a local restaurant's signature dish on camera and tag them — it
  often opens a paid collaboration conversation." For an animator: "Offer short
  animated promos to nearby shops and post them organically to get noticed."
- Concrete and actionable this week.
- Tied to a stream from the findings where sensible.

Return ONLY a JSON array, no prose, no markdown fences:
[{{"title": "...", "idea": "...", "related_stream": "affiliate"}}, ...]

HARD RULES:
- NEVER promise or estimate earnings.
- Keep each "idea" to 1-2 sentences.
- "related_stream" is optional; use a stream id from findings or omit it."""


# ─────────────────────────────────────────────────────────────────────────
#  Groq call (self-contained, optional)
# ─────────────────────────────────────────────────────────────────────────


async def _try_groq(prompt: str, *, want_json: bool) -> str | None:
    """
    Best-effort Groq completion. Returns None on any problem (missing key,
    import failure, network error) so callers fall back to heuristics.
    """
    from app.config import settings

    api_key = settings.groq_api_key
    if not api_key:
        logger.info("[earn.coach] GROQ_API_KEY not set — using heuristic narrator")
        return None

    try:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=api_key)
        resp = await client.chat.completions.create(
            model=_GROQ_MODEL,
            max_tokens=_MAX_TOKENS,
            temperature=0.6,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[earn.coach] Groq call failed (%s) — falling back", str(exc)[:160]
        )
        return None


def _parse_ideas(raw: str) -> list[CreativeIdea]:
    """Parse the model's JSON array, tolerating stray markdown fences."""
    cleaned = (
        raw.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    try:
        data = json.loads(cleaned)
        out: list[CreativeIdea] = []
        for item in data[:3]:
            if isinstance(item, dict) and item.get("idea"):
                out.append(
                    CreativeIdea(
                        title=str(item.get("title", "Idea"))[:120],
                        idea=str(item["idea"])[:400],
                        related_stream=item.get("related_stream"),
                    )
                )
        return out
    except (json.JSONDecodeError, TypeError, KeyError):
        return []


# ─────────────────────────────────────────────────────────────────────────
#  Heuristic fallbacks — guarantee the page always has content
# ─────────────────────────────────────────────────────────────────────────


def _heuristic_coaching(report: ReadinessReport) -> str:
    blurb = TIER_BLURB.get(report.tier, "")
    ready = [s.label for s in report.ranked_gaps if s.state == StreamState.GREEN_LIGHT]
    almost = [
        s.label for s in report.ranked_gaps if s.state == StreamState.ALMOST_THERE
    ]

    if ready:
        move = f"Your strongest next move is {ready[0].lower()} — you're cleared for it right now."
    elif almost:
        move = f"You're close to unlocking {almost[0].lower()}; a bit more growth gets you there."
    else:
        move = "Focus on growing and engaging your audience — the income streams open up as you do."

    note = ""
    if report.assessment.flex_reason:
        note = " " + report.assessment.flex_reason
    if report.assessment.confidence == "low":
        note += " Connect more of your accounts and this guidance gets sharper."

    return f"{blurb} {move}{note}".strip()


def _heuristic_ideas(report: ReadinessReport, niche: str | None) -> list[CreativeIdea]:
    """Generic-but-useful ideas when the LLM is unavailable."""
    n = niche or "your niche"
    ideas = [
        CreativeIdea(
            title="Feature products you already use",
            idea=f"Naturally mention tools or products central to {n} in your content, "
            f"with affiliate links — recommendations you'd make anyway become income.",
            related_stream="affiliate",
        ),
        CreativeIdea(
            title="Tag brands you admire",
            idea=f"Spotlight a brand relevant to {n} and tag them — genuine, visible enthusiasm "
            f"is how many creator-brand conversations start.",
            related_stream="brand_deals",
        ),
        CreativeIdea(
            title="Package your know-how",
            idea=f"Turn your most-asked {n} question into a short paid guide or template — "
            f"make it once, offer it to every new follower who asks.",
            related_stream="digital_products",
        ),
    ]
    return ideas
