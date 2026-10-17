"""HTTP request and response shapes for the /api/v1/agents endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.agents.models import ContentLength, ContentType, Platform, RunStatus, Tone


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    content_type: ContentType = "Text"
    platform: Platform = "Twitter"
    length: ContentLength = "Medium"
    tone: Tone = "Formal"


class GenerateResponse(BaseModel):
    run_id: str
    status: RunStatus
    message: str


class RunSnapshot(BaseModel):
    """A run's record. Progress and results come from the live events."""

    run_id: str
    status: RunStatus
    error: str | None
    created_at: datetime
    updated_at: datetime
