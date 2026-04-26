"""
Variant Prompts — three distinct angles for parallel composition.

Each prompt produces a structurally different post even given identical
facts. The key insight: you cannot ask one LLM call for "3 variants" —
they converge. You must run three separate calls with distinct system
prompts that shape reasoning from the start.


"""
from __future__ import annotations

from typing import Any

from app.agents.composer.platform_rules import PlatformRule


_SHARED_CONSTRAINTS = """\
HARD REQUIREMENTS:
- Use AT LEAST ONE specific statistic, number, or named entity from the FACTS below.
- Stay within the platform's character limit. Count every character.
- Respect the requested TONE and LENGTH exactly — they override your defaults.
- Write in the creator's voice (see PERSONA). Mirror vocabulary from the Bio/USP
  when possible. If the Bio uses "we" / "I" / industry slang, so should you.
- Treat "USER'S INTENT" as the literal reason the creator is posting. Your post
  must visibly serve that intent — not the generic topic.
- Do NOT invent facts not present in the FACTS block.
- Do NOT narrate what you're doing ("Here's my take:", "Let me explain:").

BANNED AI-TELL PHRASES (never write any of these):
"in today's world", "in today's fast-paced", "let's dive in", "let's unpack",
"let's explore", "unlock the power", "game-changer", "revolutionize",
"navigate the landscape", "at the end of the day", "it's worth noting",
"when it comes to", "in conclusion", "embark on a journey",
"in the ever-evolving", "leverage" (as a verb), "harness", "delve".

VOICE DIALS:
- Formal    → third-person where possible, precise nouns, no slang.
- Informative → declarative, short sentences, facts first.
- Casual    → first-person welcome, contractions ok, one conversational aside max.
- GenZ      → lowercase start permitted, dry wit, zero corporate-speak,
              internet-native phrasing (no emoji spam — one max).

OUTPUT FORMAT:
Return ONLY the post body text. No preamble, no explanation, no markdown fences.\
"""


HOOK_FIRST_PROMPT = """\
You are a social media copywriter. You specialize in HOOK-FIRST posts — \
the first 8 words decide whether someone reads the rest.

STYLE FOR THIS VARIANT:
- Open with a surprising claim, contrarian take, or curiosity gap
- Second line delivers the substance
- Tight rhythm: short sentences, no throat-clearing
- End with an insight or gentle call to think

HOOK PATTERNS TO CONSIDER:
- "Most people think X. The data says Y."
- "I used to believe X. Then I saw Y."
- "3 things nobody tells you about X."
- "X is about to change. Here's how."

"""


DATA_DRIVEN_PROMPT = """\
You are a social media copywriter. You specialize in DATA-DRIVEN posts — \
posts that win because they surface the one number that matters.

STYLE FOR THIS VARIANT:
- Lead with the single most striking statistic from the FACTS
- Explain what the number means in one line
- Add ONE more number for context if available
- Close with the implication for the reader

KEEP IT ANALYTICAL:
- Numbers do the persuading; your job is framing
- Short, declarative sentences
- No hedging words ("might", "could potentially")

"""


STORY_LED_PROMPT = """\
You are a social media copywriter. You specialize in STORY-LED posts — \
posts that feel human because they start with a specific scene or moment.

STYLE FOR THIS VARIANT:
- Open with a concrete scenario (who/what/when), not an abstract idea
- Pivot from the story to the insight by the middle
- Keep sentences varied in length for a conversational feel
- End on a reflection, not a hard sell

SCENE STARTERS TO CONSIDER:
- A specific situation: "A friend asked me last week..."
- A moment of realization: "I was reviewing <thing> when I noticed..."
- A contrast: "Two years ago, X was impossible. Now..."

"""


ANGLE_PROMPTS: dict[str, str] = {
    "hook_first":  HOOK_FIRST_PROMPT,
    "data_driven": DATA_DRIVEN_PROMPT,
    "story_led":   STORY_LED_PROMPT,
}


def build_user_message(
    topic: str,
    facts: list[dict[str, Any]],
    personalization: dict[str, Any],
    rule: PlatformRule,
    tone: str = "Casual",
    content_length: str = "Medium",
    raw_prompt: str | None = None,
) -> str:
    """Compose the user turn: topic + persona + facts + platform + tone/length."""
    persona_block = _format_persona(personalization)
    facts_block = _format_facts(facts)
    platform_block = _format_platform(rule)
    voice_block = _format_voice(tone, content_length, rule)
    intent_block = (raw_prompt or topic).strip()

    return (
        f"USER'S INTENT (their exact request — this is why they're posting)\n"
        f"{intent_block}\n\n"
        f"TOPIC (distilled from intent)\n{topic}\n\n"
        f"CREATOR PERSONA (mirror this voice)\n{persona_block}\n\n"
        f"VOICE & FORMAT\n{voice_block}\n\n"
        f"FACTS (use at least one, verbatim numbers)\n{facts_block}\n\n"
        f"PLATFORM CONSTRAINTS\n{platform_block}\n\n"
        f"{_SHARED_CONSTRAINTS}\n\n"
        f"Write the post now."
    )


def _format_persona(p: dict[str, Any]) -> str:
    lines = []
    mapping = [
        ("Name",        p.get("name")),
        ("Niche",       p.get("content_niche")),
        ("Goal",        p.get("content_goal")),
        ("Intent",      p.get("content_intent")),
        ("Audience",    p.get("target_audience")),
        ("Age group",   p.get("target_age_group")),
        ("Region",      p.get("target_country")),
        ("USP",         p.get("usp")),
        ("Bio (voice anchor — mimic word choices here)", p.get("bio")),
    ]
    for label, value in mapping:
        if value and str(value).strip():
            lines.append(f"- {label}: {value}")
    return "\n".join(lines) if lines else "- No persona context provided"


# Length band → target character guidance layered on top of platform rules.
# The platform's target_chars is the anchor; these dials nudge shorter / longer.
_LENGTH_DIAL: dict[str, tuple[float, float]] = {
    "Short":  (0.55, 0.80),   # 55-80% of platform target
    "Medium": (0.85, 1.15),   # near target
    "Long":   (1.20, 1.60),   # 120-160% of target, still ≤ max
}


def _format_voice(tone: str, content_length: str, rule: PlatformRule) -> str:
    lo_mul, hi_mul = _LENGTH_DIAL.get(content_length, _LENGTH_DIAL["Medium"])
    lo = max(rule.min_chars, int(rule.target_chars * lo_mul))
    hi = min(rule.max_chars, int(rule.target_chars * hi_mul))
    if hi < lo:  # tiny platforms (Twitter + Long) — clamp sensibly
        hi = rule.max_chars
    return (
        f"- Tone: {tone}\n"
        f"- Length band: aim for {lo}-{hi} characters (hard max {rule.max_chars})\n"
        f"- Structure: {rule.structure.replace('_', ' ')}"
    )


def _format_facts(facts: list[dict[str, Any]]) -> str:
    if not facts:
        return "- (no distilled facts available — rely on topic)"
    return "\n".join(
        f"- [{f['type']}, source {f['source']}] {f['fact']}"
        for f in facts
    )


def _format_platform(rule: PlatformRule) -> str:
    return (
        f"- Target platform: {rule.name}\n"
        f"- Character limit: {rule.max_chars} (sweet spot: {rule.target_chars})\n"
        f"- Minimum length: {rule.min_chars} characters\n"
        f"- Format: {rule.format_hint}\n"
        f"- Hashtags: {'allowed, max ' + str(rule.max_hashtags) if rule.use_hashtags else 'NOT used on this platform'}"
    )