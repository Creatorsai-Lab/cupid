"""
Cupid Agent State - Shared state object for the LangGraph pipeline.

All agents read from and write to this typed state dict.
No agent holds internal state between runs.
"""
from __future__ import annotations

from typing import TypedDict, Literal
from datetime import datetime


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

class ComposerOutput(TypedDict, total=False):
    """Output from the Composer Agent."""
    platform: str
    content: str
    hashtags: list[str]
    confidence_score: float
    personalization_fidelity_score: float


class MemoryState(TypedDict, total=False):
    """
    Shared state for the Cupid agent pipeline.

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
    content_type: Literal["Text", "Image", "Article", "Video", "Ads", "Poll"]
    target_platform: Literal["All", "Twitter", "LinkedIn", "Instagram", "Facebook", "YouTube"]
    content_length: Literal["Short", "Medium", "Long"]
    tone: Literal["Formal", "Informative", "Casual", "GenZ"]
    # User profile context (from database)
    personalization: PersonalizationInfo
    # Agent outputs
    research_data: ResearchData
    composer_output: ComposerOutput
    # Execution tracking
    current_agent: str
    agents_completed: list[str]
    error: str | None
    status: Literal["pending", "running", "completed", "failed"]
