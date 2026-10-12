"""HTTP request and response shapes for the /api/v1/agents endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.agents.models import ContentLength, ContentType, Platform, Tone


class GenerateRequest(BaseModel):
    prompt: str
    content_type: ContentType = "Text"
    platform: Platform = "Twitter"
    length: ContentLength = "Medium"
    tone: Tone = "Formal"


class GenerateResponse(BaseModel):
    run_id: str
    status: str
    message: str


class RunStatusResponse(BaseModel):
    run_id: str
    status: Literal["pending", "running", "completed", "failed"]
    created_at: datetime
    current_agent: str | None = None
    agents_completed: list[str] = []
    error: str | None = None
    personalization_queries: list[str] = []
    research_data: dict | None = None
    trend_data: dict | None = None
    composer_output: list | None = None
    composer_evidence: list | None = None
    composer_sources: list | None = None
    history_id: str | None = None
