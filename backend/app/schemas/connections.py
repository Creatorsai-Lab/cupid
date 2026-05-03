"""
Connections schemas — Pydantic models for the connections API responses.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ConnectionResponse(BaseModel):
    """Public-facing representation of a SocialConnection.

    NEVER includes encrypted tokens — those stay server-side.
    """
    id: UUID
    platform: str = Field(..., description="e.g. 'youtube'")
    platform_user_id: str = Field(..., description="Channel ID on the platform")
    handle: str | None
    connected_at: datetime
    last_synced_at: datetime | None
    sync_status: str = Field(..., description="'idle' | 'syncing' | 'failed'")
    last_error: str | None


class ConnectionStartResponse(BaseModel):
    """Returned when user clicks 'Connect' — frontend opens this URL."""
    authorization_url: str