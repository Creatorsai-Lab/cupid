"""
TopContent model — leaderboard of a connection's best-performing content
at a point in time.

═══════════════════════════════════════════════════════════════════════════
WHY A SEPARATE TABLE?
═══════════════════════════════════════════════════════════════════════════
We could put top videos inside InsightsSnapshot.raw_data. Two reasons not to:

1. QUERY EFFICIENCY. The frontend wants:
       "Top 10 videos by views, all-time"
   Without a typed table, we'd have to JSON-extract from every snapshot
   and aggregate in Python. With a table, it's one SQL query.

2. INDIVIDUAL CONTENT TRACKING. We want to track each video's metrics
   over time too. A single video might appear in our top-10 on multiple
   days — each appearance is a row, with that day's view count.

═══════════════════════════════════════════════════════════════════════════
RANKING vs RAW DATA
═══════════════════════════════════════════════════════════════════════════
Each row carries both:
    rank (1..10)         — position in the leaderboard at time of snapshot
    views, likes, etc    — the actual numbers
This lets us answer both "what was top yesterday" and "how much did the
#3 video grow week over week."
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date, DateTime, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.user import Base

if TYPE_CHECKING:
    from app.models.social_connection import SocialConnection


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
        DateTime(timezone=True), nullable=False,
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

    connection: Mapped["SocialConnection"] = relationship()

    __table_args__ = (
        # Common query path: top-K for a connection on a date
        Index(
            "ix_top_content_connection_date_rank",
            "connection_id", "snapshot_date", "rank",
        ),
    )

    def __repr__(self) -> str:
        return f"<TopContent #{self.rank} {self.title[:30]!r} views={self.views}>"