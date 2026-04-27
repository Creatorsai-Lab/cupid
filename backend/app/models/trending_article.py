"""
TrendingArticle ORM model.

This is the table that holds articles between ingestion and serving.

Indexing notes:
    - `category`: most queries filter by niche → index it.
    - `published_at`: we sort by recency → index it descending.
    - `url_hash`: dedup check needs O(log n) lookup → unique index.

Composite index on (category, published_at DESC) would be ideal for the
common query "give me recent articles in tech" — Postgres can use it as
a sorted scan. Add that as an Alembic migration when traffic grows.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    DateTime, Float, Index, String, Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base

class TrendingArticle(Base):
    __tablename__ = "trending_articles"

    # url_hash is the primary key — deterministic dedup across runs.
    # Using sha256(url)[:32] gives us collision-free strings under 32 chars.
    url_hash:    Mapped[str]      = mapped_column(String(32), primary_key=True)

    title:       Mapped[str]      = mapped_column(String(512), nullable=False)
    description: Mapped[str|None] = mapped_column(Text, nullable=True)
    url:         Mapped[str]      = mapped_column(Text, nullable=False)
    image_url:   Mapped[str|None] = mapped_column(Text, nullable=True)

    source:      Mapped[str]      = mapped_column(String(128), nullable=False)
    domain:      Mapped[str]      = mapped_column(String(128), nullable=False, index=True)
    category:    Mapped[str]      = mapped_column(String(64),  nullable=False, index=True)

    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ingested_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Pre-computed at ingestion so serving doesn't recompute on every request
    velocity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Composite index — speeds up "recent articles in category X" queries
    __table_args__ = (
        Index("ix_trending_category_published", "category", "published_at"),
    )

    def __repr__(self) -> str:
        return f"<TrendingArticle {self.category}/{self.title[:30]!r}>"