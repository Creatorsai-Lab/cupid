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

# ── Composer types ──────────────────────────────────────────────
 
class QualityBreakdown(TypedDict):
    """Multi-axis quality score for a variant."""
    composite: float
    length_fit: float
    grounding: float
    persona_match: float
    hook_strength: float
    passes: bool
 
 
class ComposerVariant(TypedDict):
    """One generated post variant, grounded in a single source."""
    angle: Literal["hook_first", "data_driven", "story_led"]  # user-selected voice
    source_rank: int        # 1 = top source, 2 = second, 3 = third
    source_domain: str | None
    platform: str
    content: str
    hashtags: list[str]
    char_count: int
    quality: QualityBreakdown
 
 
class ComposerDistilledFact(TypedDict):
    """One atomic fact extracted from source material."""
    fact: str
    source: int
    type: Literal["stat", "quote", "entity", "claim", "relationship"]
 
 
class ComposerSource(TypedDict):
    """Compact reference to a source used for composition."""
    title: str | None
    url: str | None
    domain: str | None
    rank_score: float | None



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
    tone: Literal["Formal", "Informative", "Casual", "GenZ", "Factual", "Hook First", "Data Driven", "Story Led"]
    user_voice: Literal["hook_first", "data_driven", "story_led"]  # derived from tone in router
    # User profile context (from database)
    personalization: PersonalizationInfo
    # Agent outputs
    personalization_queries: list[str]
    research_data: ResearchData
    composer_output: list[ComposerVariant]
    composer_evidence: list[ComposerDistilledFact]
    composer_sources: list[ComposerSource]
    # Execution tracking
    current_agent: str
    agents_completed: list[str]
    error: str | None
    status: Literal["pending", "running", "completed", "failed"]
