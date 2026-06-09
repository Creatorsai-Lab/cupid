"""
Cupid Agent State - Shared state object for the LangGraph pipeline.
All agents read from and write to this typed state dict.
No agent holds internal state between runs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, TypedDict


class PersonalizationInfo(TypedDict, total=False):
    """User personalization information passed to all agents."""

    name: str
    nickname: str | None
    bio: str | None
    content_niche: str | None
    content_goal: str | None
    content_intent: str | None
    target_age_group: str | None
    target_country: str | None
    target_audience: str | None
    usp: str | None


class SearchResult(TypedDict):
    """Single search result item from web search."""

    query: str
    title: str
    url: str
    snippet: str
    domain: str
    score: float


class PageContent(TypedDict):
    """Extracted content from a web page."""

    url: str
    title: str
    domain: str
    text_content: str
    text_length: int
    image_url: str | None


class ResearchData(TypedDict, total=False):
    """Output from the Research Agent."""

    generated_keywords: list[str]
    queries_used: list[str]
    top_search_results: list[SearchResult]
    fetched_pages: list[PageContent]
    research_summary: str


# Memory fields for composer agent


class ComposerVariant(TypedDict):
    """One generated post draft (out of 3) based on the full research context."""

    draft_number: int
    platform: str
    content: str
    char_count: int


class ComposerSource(TypedDict):
    """Compact reference to a source used for composition."""

    title: str | None
    url: str | None
    domain: str | None
    rank_score: float | None


class MemoryState(TypedDict, total=False):
    """Shared state for the Cupid agent pipeline.
    This is the single source of truth that flows through all agents.
    Each agent reads what it needs and writes its output back to this state.
        Flow:
        User Input → Orchestrator
            ↓
        Personalization Agent (optional, enriches personalization)
            ↓
        Research Agent (produces research_data)
            ↓
        Composer Agent (produces composer_output)
    """

    # Request metadata
    run_id: str
    user_id: str
    created_at: datetime
    # User input
    user_prompt: str
    content_type: Literal["Text", "Image", "Article", "Video", "Ads", "Quiz"]
    target_platform: Literal[
        "Twitter", "LinkedIn", "Instagram", "Facebook", "YouTube", "Web"
    ]
    content_length: Literal["Short", "Medium", "Long", "Full Article"]
    tone: Literal[
        "Casual",
        "Formal",
        "Informative",
        "GenZ",
        "Factual",
        "Hook First",
        "Data Driven",
        "Story Led",
        "Lifestyle",
    ]

    # User profile context (from database)
    personalization: PersonalizationInfo
    # Agent outputs
    personalization_queries: list[str]
    research_data: ResearchData
    composer_output: list[ComposerVariant]
    composer_sources: list[ComposerSource]
    # Execution tracking
    current_agent: str
    agents_completed: list[str]
    error: str | None
    status: Literal["pending", "running", "completed", "failed"]
