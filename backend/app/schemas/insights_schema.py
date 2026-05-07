"""
Insights API schemas - the contract between backend and frontend.

ONE SCHEMA PER ENDPOINT
Each endpoint returns a different shape because the frontend renders
different visualizations:
    summary     → big number cards
    timeseries  → line chart
    top-content → leaderboard table
    heatmap     → 2D grid

Each gets its own Pydantic model so the frontend has type-safe contracts
and the OpenAPI docs are clear.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


# Summary (stat cards)

class SummaryResponse(BaseModel):
    """Headline numbers for the top of the insights dashboard."""
    connection_id: UUID
    handle: str | None
    platform: str

    # Current values
    subscriber_count: int
    total_views: int
    total_videos: int
    total_engagement: int

    # 30-day deltas
    subscriber_delta_30d: int = Field(
        ..., description="Change in subscribers over the last 30 days"
    )
    views_delta_30d: int = Field(
        ..., description="Change in total views over the last 30 days"
    )

    # Sync metadata
    last_synced_at: datetime | None
    sync_status: str


# ─── Time series (line chart data) ─────────────────────────────

class TimeSeriesPoint(BaseModel):
    """One data point in a time series chart."""
    date: date
    follower_count: int
    total_views: int
    follower_delta: int
    views_delta: int


class TimeSeriesResponse(BaseModel):
    """Sequence of daily snapshots — frontend feeds this to Recharts."""
    connection_id: UUID
    points: list[TimeSeriesPoint]
    range_days: int


# ─── Top content (leaderboard) ─────────────────────────────────

class TopContentItem(BaseModel):
    """One row in the top videos table."""
    rank: int
    content_id: str
    title: str
    url: str
    thumbnail_url: str | None
    published_at: datetime
    views: int
    likes: int
    comments: int


class TopContentResponse(BaseModel):
    """Today's top-N most-viewed videos for this connection."""
    connection_id: UUID
    snapshot_date: date
    items: list[TopContentItem]


# ─── Heatmap (best posting times) ──────────────────────────────

class HeatmapCell(BaseModel):
    """One cell of the day-of-week × hour grid."""
    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    hour: int = Field(..., ge=0, le=23)
    avg_views: float
    post_count: int


class HeatmapResponse(BaseModel):
    """Posting time vs engagement heatmap, computed from top videos."""
    connection_id: UUID
    cells: list[HeatmapCell]
    insight: str = Field(
        ...,
        description="Human-readable hint about best posting time, e.g. "
                    "'Your best performing videos publish on Tuesdays at 18:00'",
    )