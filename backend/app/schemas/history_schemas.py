"""
History schemas — API response shapes for the history feature.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class HistoryVariant(BaseModel):
    """One generated post variant within a history entry."""

    angle: str
    platform: str
    content: str
    char_count: int


class HistoryEntry(BaseModel):
    """A single saved creation, returned in the history list and detail."""

    id: UUID
    prompt: str
    target_platform: str
    tone: str | None
    variants: list[HistoryVariant]
    created_at: datetime


class HistoryListResponse(BaseModel):
    """Paginated list of history entries, newest first."""

    entries: list[HistoryEntry]
    total: int = Field(..., description="Total entries for this user")
    has_more: bool = Field(..., description="Whether more pages exist")


class HistoryUpdateRequest(BaseModel):
    """Body for editing the variants of a saved creation."""

    variants: list[HistoryVariant]
