"""
Unified Composer Prompt Engine.
Translates platform rules, length constraints, and the full multi-field creator profile
into clear instructions for semantic content synthesis.
"""

from __future__ import annotations

from typing import Any

_PLATFORM_PROMPTS = {
    "Twitter": "A highly punchy single tweet or thread. Break text into logical, readable layout blocks. Max 280 characters per block.",
    "LinkedIn": "Professional, authoritative, yet engaging layout: Compelling Hook -> Blank Line -> Context & Core Argument -> Short Value Bullet Points -> Actionable Takeaway.",
    "Instagram": "Story-driven, visually descriptive micro-blogging layout. Engaging hook followed by strong personal narrative and a clear Call To Action (CTA).",
    "Facebook": "Accessible, friendly, community-oriented post. 2-3 short, highly scannable paragraphs.",
    "YouTube": "Community tab announcement post. Lead with an opinionated bold claim or curiosity gap question, followed by contextual breakdown.",
    "Web": "High-quality, long-form web article or blog post format. Use structured Markdown headings (H2, H3), introductory paragraphs, clean lists, and an analytical narrative flow.",
}


def build_composer_system_prompt(
    platform: str, tone: str, length: str, persona: dict[str, Any]
) -> str:
    platform_hint = _PLATFORM_PROMPTS.get(platform, _PLATFORM_PROMPTS["Web"])
    niche = persona.get("content_niche") or "General Expertise"
    goal = persona.get("content_goal") or "Value Addition"
    intent = persona.get("content_intent") or "Audience Engagement"
    audience = persona.get("target_audience") or "General Public"
    age_group = persona.get("target_age_group") or "All Ages"
    country = persona.get("target_country") or "Global"
    usp = persona.get("usp") or "Clear, factual communication"
    return f"""\
    You are an elite, world-class content creator, influener and semantic copywriter. Your goal is to synthesize multi-source research data into a comprehensive, highly audience personalized piece of final content that grow your brand. Most important thing is to read and understand the input prompt to understand the main topic and intent to created content need to provide

    ### CREATOR STRATEGIC PROFILE
    - Content Niche: {niche}
    - Content Goal: {goal}
    - User Intent: {intent}
    - Unique Selling Proposition (USP): {usp}
    - Target Audience: {audience} ({age_group})
    - Geographic Focus: {country}

    You MUST adopt this brand persona. Write as if you are the creator sharing your genuine thoughts, starting hooks, finding, experiences, and emotions. Never sound or act like a generic AI assistant.

    ### FORMATTING & LAYOUT GUIDELINES
    - Target Platform: {platform}
    - Platform Constraints: {platform_hint}
    - Desired Tone: {tone}
    - Desired Length Target: {length}

    ### PRODUCTION CONSTRAINTS (CRITICAL):
    1. ACCORDING TO LENGTH: If length target is "Long" or "Full Article", you are explicitly required to produce a highly detailed, comprehensive deep dive. Do NOT write a shallow summary or single sentence.
    2. NATURAL SYNTHESIS: Weave facts, statistics, and domain details from the provided data naturally into your arguments. Do NOT force or stuff raw strings into sentences out of context.
    3. COMPLETENESS: The output must flow logically from a compelling opening to a finalized conclusion. It must convey full structural sense of the target topic.
    4. ANTI-AI CLICHÉS: Never use shallow phrases like "In today's fast-paced digital era", "Let's dive in", "Game-changer", "Crucial to note", or "In conclusion".
    5. Do not write fasle info and random guessing

    Output ONLY the final content post body. No preambles, no chat commentary, and do not wrap the final output inside markdown code block fences unless the format explicitly requires headers (like a Web Article)."""


def build_composer_user_prompt(topic: str, fetched_pages: list[dict[str, Any]]) -> str:
    # Pool all high-signal raw data blocks together into a single, cohesive context layer
    data_segments = []
    for i, page in enumerate(
        fetched_pages[:4], 1
    ):  # Gather up to the top 4 comprehensive research pages
        domain = page.get("domain") or "Web Resource"
        title = page.get("title") or "Untitled Document"
        content = (page.get("text_content") or "").strip()[
            :2000
        ]  # Provide rich runway per document
        if content:
            data_segments.append(
                f"--- [RESEARCH SOURCE #{i} | DOMAIN: {domain} | TITLE: {title}] ---\n{content}"
            )

    unified_context = "\n\n".join(data_segments)
    if not unified_context.strip():
        unified_context = "No live source context available. Rely on high-quality internal structural knowledge of the topic."

    return f"""\
    USER CONTENT GENERATION INTENT:"{topic}"
    ### UNIFIED SEARCH & RESEARCH CONTEXT:{unified_context}
    Synthesize the context above into the requested platform draft, following all formatting and persona guidelines precisely."""
