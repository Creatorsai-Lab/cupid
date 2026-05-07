r"""
Sync Orchestrator — pulls fresh data for one connection and writes
snapshots to the DB.

Token refresh as a transparent middleware. Higher-level code (sync.py) never thinks about token expiry. It just calls get_valid_access_token() and trusts it. 
This is the same pattern Stripe, Slack, and every well-built OAuth-consuming service uses.

UPSERT vs DELETE+INSERT for different data shapes. Snapshots are one-row-per-day-per-connection — UPSERT lets multiple syncs update the same row. Top content is ten-rows-per-day-per-connection — UPSERT would accumulate, so we DELETE then INSERT atomically.


1. THE FULL FLOW (PER CONNECTION)
---------------------------------
    1. Mark connection.sync_status = 'syncing'
    2. Get a valid access token (refresh if needed)
    3. Fetch channel stats from YouTube
    4. Fetch top recent videos from YouTube
    5. Compute deltas vs previous snapshot
    6. UPSERT today's row in insights_snapshots
    7. Replace today's rows in top_content with new top-10
    8. Mark connection.sync_status = 'idle' and update last_synced_at
    9. On any exception: status = 'failed', store error message

2. WHY UPSERT FOR SNAPSHOTS, REPLACE FOR TOP_CONTENT
-------------------------------------------------
SNAPSHOTS: one row per (connection, date). If sync runs 4 times today,
the last sync's numbers win — we don't want 4 conflicting rows for
the same date. UPSERT (insert ... on conflict update) is the right tool.

TOP_CONTENT: 10 rows per (connection, date). If we UPSERT we'd accumulate
ranks 1..10 from each sync, ending with 40 rows for today. Instead we
DELETE today's rows and INSERT fresh ones. Atomic within a transaction.

2. ERROR ISOLATION
------------------
This function is wrapped in a try/except such that a failure for ONE
connection doesn't kill the scheduler. The scheduler runs many connections
in sequence — one bad token shouldn't block the others.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.insights import youtube_client
from app.insights.token_manager import (
    TokenRefreshFailed, get_valid_access_token,
)
from app.insights.youtube_client import YouTubeAPIError
from app.models.insights_snapshot import InsightsSnapshot
from app.models.social_connection import SocialConnection
from app.models.top_content import TopContent

logger = logging.getLogger(__name__)


async def sync_connection(
    connection_id: UUID,
    session: AsyncSession,
) -> dict[str, int]:
    """
    Pull fresh data from YouTube and persist a new snapshot + top videos.

    Returns a summary dict for logging:
        {"videos_fetched": N, "snapshot_id": str, ...}

    Raises:
        ValueError if the connection doesn't exist.
        Other errors are caught internally and recorded on the connection.
    """
    # Load connection (no eager load — we update fields and commit later)
    connection = await session.get(SocialConnection, connection_id)
    if connection is None:
        raise ValueError(f"Connection {connection_id} not found")

    if connection.platform != "youtube":
        raise ValueError(
            f"sync_connection only supports youtube; got {connection.platform!r}"
        )

    # Mark as syncing — surfaces in UI as "syncing..."
    connection.sync_status = "syncing"
    connection.last_error = None
    await session.commit()

    try:
        # 1) Get a valid access token (refreshes automatically if needed)
        access_token = await get_valid_access_token(connection, session)

        # 2) Fetch fresh data from YouTube
        channel_stats = await youtube_client.get_channel_stats(access_token)
        videos = await youtube_client.get_recent_videos(
            access_token, max_results=25,
        )

        logger.info(
            "[sync] %s: %d subs, %d videos fetched",
            connection.handle or connection.platform_user_id,
            channel_stats["subscriber_count"], len(videos),
        )

        # 3) Compute today's snapshot
        today = date.today()
        snapshot = await _upsert_snapshot(
            session, connection, today, channel_stats, videos,
        )

        # 4) Replace today's top content
        await _replace_top_content(session, connection.id, today, videos)

        # 5) Mark sync complete
        connection.sync_status = "idle"
        connection.last_synced_at = datetime.now(timezone.utc)
        await session.commit()

        return {
            "snapshot_id":     str(snapshot.id),
            "subscribers":     channel_stats["subscriber_count"],
            "videos_fetched":  len(videos),
            "follower_delta":  snapshot.follower_delta,
        }

    except TokenRefreshFailed as exc:
        # User revoked access — mark for reconnect
        connection.sync_status = "failed"
        connection.last_error = (
            "Access revoked. Please disconnect and reconnect YouTube."
        )
        await session.commit()
        logger.warning(
            "[sync] %s: token refresh failed: %s", connection_id, exc,
        )
        raise

    except YouTubeAPIError as exc:
        # API-level error — store details for debugging
        connection.sync_status = "failed"
        connection.last_error = f"YouTube API: {exc}"
        await session.commit()
        logger.warning(
            "[sync] %s: YouTube API error: %s", connection_id, exc,
        )
        raise

    except Exception as exc:
        # Anything else — DB error, network blip, etc.
        connection.sync_status = "failed"
        connection.last_error = f"Unexpected: {exc}"
        await session.commit()
        logger.exception("[sync] %s: unexpected error", connection_id)
        raise


# ──────────────────────────────────────────────────────────────────
#  Snapshot upsert
# ──────────────────────────────────────────────────────────────────

async def _upsert_snapshot(
    session: AsyncSession,
    connection: SocialConnection,
    snapshot_date: date,
    channel: youtube_client.ChannelStats,
    videos: list[youtube_client.VideoStats],
) -> InsightsSnapshot:
    """
    Insert today's snapshot or update if one already exists.
    Computes deltas vs the most recent prior snapshot.
    """
    # Find the most recent previous snapshot to compute deltas against
    prev_stmt = (
        select(InsightsSnapshot)
        .where(InsightsSnapshot.connection_id == connection.id)
        .where(InsightsSnapshot.snapshot_date < snapshot_date)
        .order_by(InsightsSnapshot.snapshot_date.desc())
        .limit(1)
    )
    prev = (await session.execute(prev_stmt)).scalar_one_or_none()

    follower_delta = (
        channel["subscriber_count"] - prev.follower_count
        if prev else 0
    )
    views_delta = (
        channel["total_views"] - prev.total_views
        if prev else 0
    )

    # Total engagement = sum of likes + comments across recent videos
    total_engagement = sum(v["views"] + v["likes"] + v["comments"] for v in videos)

    # Build the row payload
    row_data = {
        "connection_id":       connection.id,
        "snapshot_date":       snapshot_date,
        "follower_count":      channel["subscriber_count"],
        "total_content_count": channel["total_videos"],
        "total_views":         channel["total_views"],
        "total_engagement":    total_engagement,
        "follower_delta":      follower_delta,
        "views_delta":         views_delta,
        "raw_data": {
            "channel": channel,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    # PostgreSQL UPSERT on (connection_id, snapshot_date)
    stmt = insert(InsightsSnapshot).values(**row_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["connection_id", "snapshot_date"],
        set_={
            "follower_count":      stmt.excluded.follower_count,
            "total_content_count": stmt.excluded.total_content_count,
            "total_views":         stmt.excluded.total_views,
            "total_engagement":    stmt.excluded.total_engagement,
            "follower_delta":      stmt.excluded.follower_delta,
            "views_delta":         stmt.excluded.views_delta,
            "raw_data":            stmt.excluded.raw_data,
        },
    ).returning(InsightsSnapshot)

    result = await session.execute(stmt)
    return result.scalar_one()


# ──────────────────────────────────────────────────────────────────
#  Top content replace
# ──────────────────────────────────────────────────────────────────

async def _replace_top_content(
    session: AsyncSession,
    connection_id: UUID,
    snapshot_date: date,
    videos: list[youtube_client.VideoStats],
    top_k: int = 10,
) -> None:
    """
    Wipe today's top_content rows for this connection, write fresh ones.

    "Top" = sorted by views, descending. Take the top K.
    """
    # Delete today's existing rows
    await session.execute(
        delete(TopContent)
        .where(TopContent.connection_id == connection_id)
        .where(TopContent.snapshot_date == snapshot_date)
    )

    # Sort videos by views and take top K
    sorted_videos = sorted(videos, key=lambda v: v["views"], reverse=True)[:top_k]

    # Insert new rows
    rows = []
    for rank, video in enumerate(sorted_videos, start=1):
        rows.append(TopContent(
            connection_id=connection_id,
            snapshot_date=snapshot_date,
            rank=rank,
            content_id=video["video_id"],
            title=video["title"][:512],
            url=f"https://www.youtube.com/watch?v={video['video_id']}",
            thumbnail_url=video["thumbnail_url"],
            published_at=_ensure_aware(video["published_at"]),
            views=video["views"],
            likes=video["likes"],
            comments=video["comments"],
            shares=None,   # YouTube doesn't expose share counts
        ))

    session.add_all(rows)


def _ensure_aware(dt: datetime) -> datetime:
    """Naïve datetimes get treated as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)