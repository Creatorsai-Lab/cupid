"""
Trends Schemas — Pydantic response models.
This file is the contract between backend and frontend. It defines exactly
what the API returns. Both ends agree on these shapes.

Why Pydantic?
    FastAPI uses Pydantic models to auto-generate OpenAPI docs, validate
    responses, and serialize to JSON. We get type safety + free Swagger UI.

Why two separate models (Article + Response)?
    The frontend doesn't need to know about pagination, ranking metadata,
    or cache state on every article. We send one envelope (Response) that
    contains a list of clean Articles plus high-level metadata.
"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl

class TrendingArticle(BaseModel):
    """One news article ranked into the user's trend feed."""
    id: str = Field(..., description="Stable article ID (URL hash)")
    title: str
    description: str | None = None
    url: HttpUrl
    image_url: HttpUrl | None = None
    source: str = Field(..., description="Publisher name, e.g. 'TechCrunch'")
    domain: str = Field(..., description="e.g. 'techcrunch.com'")
    published_at: datetime
    category: str = Field(..., description="Niche bucket, e.g. 'technology'")

    # Ranking fields — useful for the frontend if we want to show a trend score
    relevance_score: float = Field(0.0, description="How well it matches user persona")
    velocity_score: float = Field(0.0, description="Recency + source authority composite")


class TrendsResponse(BaseModel):
    """Wraps the article list with metadata about the request."""
    articles: list[TrendingArticle]
    niche: str = Field(..., description="The niche we ranked against")
    total_pool: int = Field(..., description="How many articles we ranked from")
    cached: bool = Field(False, description="Whether this came from Redis cache")
    generated_at: datetime