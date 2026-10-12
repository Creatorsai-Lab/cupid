"""
InsightsSnapshot model — time-series of analytics data, one row per
connection per day.

═══════════════════════════════════════════════════════════════════════════
WHY TIME-SERIES?
═══════════════════════════════════════════════════════════════════════════
The user wants to see GROWTH over time. "Subscribers over the last 30
days" needs 30 daily data points. We can't compute growth from a single
current snapshot — we need history.

Append-only: every sync inserts a new row. Old rows never change. This
makes growth charts trivial:
    SELECT snapshot_date, follower_count
      FROM insights_snapshots
     WHERE connection_id = :id
       AND snapshot_date >= NOW() - INTERVAL '30 days'
     ORDER BY snapshot_date

═══════════════════════════════════════════════════════════════════════════
WHY UNIVERSAL FIELDS + RAW BLOB?
═══════════════════════════════════════════════════════════════════════════
Different platforms expose different metrics. YouTube has watch_time,
subscriber demographics. Instagram has reach, impressions. LinkedIn has
post-level engagement.

We extract a few UNIVERSAL fields into typed columns (every platform
has them — followers, total views, engagement) so we can query them
efficiently. Everything else goes into the `raw_data` JSONB column
preserved in its native shape.

When YouTube adds a new metric next month, our existing schema still
works — the new metric is automatically captured in raw_data, and we
extract it into a typed column only if we decide to query/chart it.

This is the "extracted highlights + flexible blob" pattern from Stripe
and Segment. Standard for ingesting third-party API data.
═══════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.connections.models import SocialConnection


class InsightsSnapshot(Base):
    __tablename__ = "insights_snapshots"

    # ── Primary key ─────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Foreign key ─────────────────────────────────────────────
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("social_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── When ────────────────────────────────────────────────────
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Granularity: one row per day. If the sync runs multiple times
    # in a day (e.g. every 6h), we UPSERT on (connection_id, snapshot_date)
    # so the latest sync wins and we keep daily granularity.

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Universal metrics (every platform) ──────────────────────
    follower_count: Mapped[int] = mapped_column(Integer, default=0)
    total_content_count: Mapped[int] = mapped_column(Integer, default=0)
    # Videos for YouTube, posts for LinkedIn, reels for IG, etc.

    total_views: Mapped[int] = mapped_column(Integer, default=0)
    total_engagement: Mapped[int] = mapped_column(Integer, default=0)
    # Engagement = sum of likes + comments + shares (platform-dependent
    # which we collapse into one number for the universal view).

    # ── Computed deltas vs prior snapshot ───────────────────────
    follower_delta: Mapped[int] = mapped_column(Integer, default=0)
    views_delta: Mapped[int] = mapped_column(Integer, default=0)
    # Pre-computed at sync time so the API doesn't have to compute on
    # every read. Same precompute-vs-compute trade-off as velocity_score
    # in your trends ranker.

    # ── Platform-specific raw blob ──────────────────────────────
    raw_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    # JSONB lets us query specific keys via Postgres operators if we
    # ever need to. E.g. raw_data->'demographics'->'age_18_24'.
    # Stored efficiently and indexable.

    # ── Relationship ────────────────────────────────────────────
    connection: Mapped[SocialConnection] = relationship()

    __table_args__ = (
        # One snapshot per connection per day. UPSERT target.
        UniqueConstraint(
            "connection_id",
            "snapshot_date",
            name="uq_connection_date",
        ),
        # Common query: "give me snapshots for this connection in date range"
        Index(
            "ix_snapshot_connection_date",
            "connection_id",
            "snapshot_date",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<InsightsSnapshot {self.connection_id}/{self.snapshot_date} "
            f"followers={self.follower_count}>"
        )


# TopContent model — leaderboard of a connection's best-performing content
# at a point in time.
#
# ═══════════════════════════════════════════════════════════════════════════
# WHY A SEPARATE TABLE?
# ═══════════════════════════════════════════════════════════════════════════
# We could put top videos inside InsightsSnapshot.raw_data. Two reasons not to:
#
# 1. QUERY EFFICIENCY. The frontend wants:
#        "Top 10 videos by views, all-time"
#    Without a typed table, we'd have to JSON-extract from every snapshot
#    and aggregate in Python. With a table, it's one SQL query.
#
# 2. INDIVIDUAL CONTENT TRACKING. We want to track each video's metrics
#    over time too. A single video might appear in our top-10 on multiple
#    days — each appearance is a row, with that day's view count.
#
# ═══════════════════════════════════════════════════════════════════════════
# RANKING vs RAW DATA
# ═══════════════════════════════════════════════════════════════════════════
# Each row carries both:
#     rank (1..10)         — position in the leaderboard at time of snapshot
#     views, likes, etc    — the actual numbers
# This lets us answer both "what was top yesterday" and "how much did the
# #3 video grow week over week."
# ═══════════════════════════════════════════════════════════════════════════
class TopContent(Base):
    __tablename__ = "top_content"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("social_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    # 1 = best, 10 = 10th best on this snapshot date.

    # ── Content identification ──────────────────────────────────
    content_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Platform's ID for the content. YouTube video ID like "dQw4w9WgXcQ".

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # ── Engagement metrics (universal across platforms) ─────────
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # YouTube doesn't expose share count directly. Nullable for that.

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    connection: Mapped[SocialConnection] = relationship()

    __table_args__ = (
        # Common query path: top-K for a connection on a date
        Index(
            "ix_top_content_connection_date_rank",
            "connection_id",
            "snapshot_date",
            "rank",
        ),
    )

    def __repr__(self) -> str:
        return f"<TopContent #{self.rank} {self.title[:30]!r} views={self.views}>"
