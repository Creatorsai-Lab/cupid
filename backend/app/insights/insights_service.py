"""
Insights Service — DB queries that power the API endpoints.

═══════════════════════════════════════════════════════════════════════════
DESIGN
═══════════════════════════════════════════════════════════════════════════
Each function does one job: take a connection_id and return data shaped
for one specific endpoint. Functions don't talk to each other; they
each go straight to the DB. This keeps each query focused and easy to
optimize independently.

═══════════════════════════════════════════════════════════════════════════
WHY NO REDIS CACHE LAYER (FOR NOW)
═══════════════════════════════════════════════════════════════════════════
Your trends service uses cache-aside because the DB query is expensive
(60-row pool + BM25 ranking ~85ms). Insights queries are cheap — most
hit a single index and return <30 rows. Sub-50ms on cache miss anyway.

If you ever measure these endpoints and find them slow at scale, layer
Redis the same way trends does. For MVP, skip the complexity.
═══════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.insights_snapshot import InsightsSnapshot
from app.models.social_connection import SocialConnection
from app.models.top_content import TopContent
from app.schemas.insights_schema import (
    HeatmapCell,
    HeatmapResponse,
    SummaryResponse,
    TimeSeriesPoint,
    TimeSeriesResponse,
    TopContentItem,
    TopContentResponse,
)

logger = logging.getLogger(__name__)


# ─── Summary ───────────────────────────────────────────────────


async def get_summary(
    connection: SocialConnection,
    session: AsyncSession,
) -> SummaryResponse:
    """
    Return headline numbers + 30-day deltas.

    Three queries:
        1. Latest snapshot (today's numbers)
        2. Snapshot from ~30 days ago (baseline for delta)
    """
    # Latest snapshot
    latest_stmt = (
        select(InsightsSnapshot)
        .where(InsightsSnapshot.connection_id == connection.id)
        .order_by(InsightsSnapshot.snapshot_date.desc())
        .limit(1)
    )
    latest = (await session.execute(latest_stmt)).scalar_one_or_none()

    if latest is None:
        # No data yet — return zeros so frontend can show "syncing..."
        return SummaryResponse(
            connection_id=connection.id,
            handle=connection.handle,
            platform=connection.platform,
            subscriber_count=0,
            total_views=0,
            total_videos=0,
            total_engagement=0,
            subscriber_delta_30d=0,
            views_delta_30d=0,
            last_synced_at=connection.last_synced_at,
            sync_status=connection.sync_status,
        )

    # Find the snapshot closest to 30 days ago for the delta baseline
    thirty_days_ago = date.today() - timedelta(days=30)
    baseline_stmt = (
        select(InsightsSnapshot)
        .where(InsightsSnapshot.connection_id == connection.id)
        .where(InsightsSnapshot.snapshot_date <= thirty_days_ago)
        .order_by(InsightsSnapshot.snapshot_date.desc())
        .limit(1)
    )
    baseline = (await session.execute(baseline_stmt)).scalar_one_or_none()

    if baseline is None:
        # Less than 30 days of data — show 0 delta. Honest, not made up.
        sub_delta = 0
        views_delta = 0
    else:
        sub_delta = latest.follower_count - baseline.follower_count
        views_delta = latest.total_views - baseline.total_views

    return SummaryResponse(
        connection_id=connection.id,
        handle=connection.handle,
        platform=connection.platform,
        subscriber_count=latest.follower_count,
        total_views=latest.total_views,
        total_videos=latest.total_content_count,
        total_engagement=latest.total_engagement,
        subscriber_delta_30d=sub_delta,
        views_delta_30d=views_delta,
        last_synced_at=connection.last_synced_at,
        sync_status=connection.sync_status,
    )


# ─── Time series ───────────────────────────────────────────────


async def get_timeseries(
    connection: SocialConnection,
    session: AsyncSession,
    range_days: int = 30,
) -> TimeSeriesResponse:
    """
    Return daily snapshots for the last N days, oldest-first.

    Frontend feeds this directly to Recharts <LineChart>.
    """
    since = date.today() - timedelta(days=range_days)

    stmt = (
        select(InsightsSnapshot)
        .where(InsightsSnapshot.connection_id == connection.id)
        .where(InsightsSnapshot.snapshot_date >= since)
        .order_by(InsightsSnapshot.snapshot_date.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()

    points = [
        TimeSeriesPoint(
            date=row.snapshot_date,
            follower_count=row.follower_count,
            total_views=row.total_views,
            follower_delta=row.follower_delta,
            views_delta=row.views_delta,
        )
        for row in rows
    ]

    return TimeSeriesResponse(
        connection_id=connection.id,
        points=points,
        range_days=range_days,
    )


# ─── Top content ───────────────────────────────────────────────


async def get_top_content(
    connection: SocialConnection,
    session: AsyncSession,
    limit: int = 10,
) -> TopContentResponse:
    """
    Today's top-N videos for this connection. Sorted by rank (1 = best).
    """
    today = date.today()

    stmt = (
        select(TopContent)
        .where(TopContent.connection_id == connection.id)
        .where(TopContent.snapshot_date == today)
        .order_by(TopContent.rank.asc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()

    if not rows:
        # Maybe today's sync hasn't run — fall back to most recent date
        latest_date_stmt = (
            select(TopContent.snapshot_date)
            .where(TopContent.connection_id == connection.id)
            .order_by(TopContent.snapshot_date.desc())
            .limit(1)
        )
        latest_date = (await session.execute(latest_date_stmt)).scalar_one_or_none()

        if latest_date is None:
            # No data at all
            return TopContentResponse(
                connection_id=connection.id,
                snapshot_date=today,
                items=[],
            )

        # Re-query with the actual latest date
        stmt = (
            select(TopContent)
            .where(TopContent.connection_id == connection.id)
            .where(TopContent.snapshot_date == latest_date)
            .order_by(TopContent.rank.asc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).scalars().all()
        today = latest_date

    items = [
        TopContentItem(
            rank=row.rank,
            content_id=row.content_id,
            title=row.title,
            url=row.url,
            thumbnail_url=row.thumbnail_url,
            published_at=row.published_at,
            views=row.views,
            likes=row.likes,
            comments=row.comments,
        )
        for row in rows
    ]

    return TopContentResponse(
        connection_id=connection.id,
        snapshot_date=today,
        items=items,
    )


# ─── Heatmap (posting times analysis) ──────────────────────────


async def get_heatmap(
    connection: SocialConnection,
    session: AsyncSession,
) -> HeatmapResponse:
    """
    Day-of-week × hour heatmap of average views.

    Aggregates across every video we've ever stored for this connection
    in top_content. Each cell shows: average views for videos posted at
    this day×hour.

    Insight string surfaces the best cell as a human-readable hint.
    """
    # Pull all top_content rows we have for this connection
    stmt = select(TopContent).where(TopContent.connection_id == connection.id)
    rows = (await session.execute(stmt)).scalars().all()

    # Bucket by (day_of_week, hour) — accumulate sums and counts
    buckets: dict[tuple[int, int], dict[str, int | float]] = defaultdict(
        lambda: {"sum_views": 0, "count": 0}
    )

    seen_video_ids: set[str] = (
        set()
    )  # dedupe: same video may appear in multiple snapshots

    for row in rows:
        if row.content_id in seen_video_ids:
            continue
        seen_video_ids.add(row.content_id)

        published = row.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=UTC)

        # Convert to user's local-ish time. For MVP we use UTC.
        # Future enhancement: store user timezone, convert here.
        dow = published.weekday()  # 0 = Monday, 6 = Sunday
        hour = published.hour

        bucket = buckets[(dow, hour)]
        bucket["sum_views"] += row.views
        bucket["count"] += 1

    # Build cells
    cells = [
        HeatmapCell(
            day_of_week=dow,
            hour=hour,
            avg_views=bucket["sum_views"] / bucket["count"],
            post_count=bucket["count"],
        )
        for (dow, hour), bucket in buckets.items()
    ]

    # Compute the human-readable insight
    insight = _build_heatmap_insight(cells)

    return HeatmapResponse(
        connection_id=connection.id,
        cells=cells,
        insight=insight,
    )


def _build_heatmap_insight(cells: list[HeatmapCell]) -> str:
    """Find the best-performing day×hour and describe it."""
    if not cells:
        return "Not enough video data yet to detect posting patterns."

    # Need at least a few data points to make any claim
    eligible = [c for c in cells if c.post_count >= 2]
    if not eligible:
        return "Post a few more videos to unlock posting-time insights."

    best = max(eligible, key=lambda c: c.avg_views)
    days = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    return (
        f"Your best-performing videos publish on {days[best.day_of_week]}s "
        f"around {best.hour:02d}:00 (avg {int(best.avg_views):,} views)."
    )
