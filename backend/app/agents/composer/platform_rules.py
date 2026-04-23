"""
Platform Rules — hard constraints per target platform.

Single source of truth for length limits, hashtag conventions, and
format guidance used by both prompt construction and quality scoring.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Platform = Literal[
    "All", "Twitter", "LinkedIn", "Instagram", "Facebook", "YouTube"
]


@dataclass(frozen=True)
class PlatformRule:
    """Hard + soft constraints for composing content on this platform."""
    name: str
    max_chars: int
    target_chars: int        # sweet spot for engagement
    min_chars: int           # too short looks lazy
    use_hashtags: bool
    max_hashtags: int
    format_hint: str         # one-line guidance injected into prompt
    structure: str           # "single_block" | "threaded" | "paragraphs"


PLATFORM_RULES: dict[str, PlatformRule] = {
    "Twitter": PlatformRule(
        name="Twitter/X",
        max_chars=280,
        target_chars=240,
        min_chars=60,
        use_hashtags=True,
        max_hashtags=2,
        format_hint="Punchy single tweet. Hook in first 8 words. No emojis unless essential.",
        structure="single_block",
    ),
    "LinkedIn": PlatformRule(
        name="LinkedIn",
        max_chars=2200,
        target_chars=1300,
        min_chars=400,
        use_hashtags=True,
        max_hashtags=5,
        format_hint="Hook line → blank line → 2-4 short paragraphs → blank line → key takeaway. Professional voice.",
        structure="paragraphs",
    ),
    "Facebook": PlatformRule(
        name="Facebook",
        max_chars=500,
        target_chars=280,
        min_chars=80,
        use_hashtags=False,
        max_hashtags=0,
        format_hint="Conversational, like talking to a friend. 2-3 short paragraphs.",
        structure="paragraphs",
    ),
    "Instagram": PlatformRule(
        name="Instagram",
        max_chars=2200,
        target_chars=500,
        min_chars=100,
        use_hashtags=True,
        max_hashtags=10,
        format_hint="Hook → story in 3-4 short lines → CTA. Line breaks between thoughts.",
        structure="paragraphs",
    ),
    "YouTube": PlatformRule(
        name="YouTube",
        max_chars=1500,
        target_chars=700,
        min_chars=200,
        use_hashtags=True,
        max_hashtags=3,
        format_hint="Community post style. Question or bold claim up top. Then context.",
        structure="paragraphs",
    ),
    "All": PlatformRule(
        name="Multi-platform",
        max_chars=500,
        target_chars=280,
        min_chars=80,
        use_hashtags=True,
        max_hashtags=3,
        format_hint="Platform-agnostic. Lead with hook, keep it punchy and shareable.",
        structure="single_block",
    ),
}


def rule_for(platform: str | None) -> PlatformRule:
    """Resolve platform name to its rule. Falls back to 'All'."""
    return PLATFORM_RULES.get(platform or "All", PLATFORM_RULES["All"])