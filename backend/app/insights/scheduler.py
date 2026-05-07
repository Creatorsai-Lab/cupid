"""
Insights Scheduler - drift-tolerant background sync for all YouTube connections.

1. DEV STRATEGY (this file)
---------------------------
Runs as a single asyncio task spawned by FastAPI's lifespan. On wake:
    1. Load all youtube connections that haven't synced in >X hours
    2. Sync each one sequentially (skip on individual failures)
    3. Sleep for INTERVAL_HOURS
    4. Repeat

Same drift-tolerant pattern as your trends scheduler — handles "laptop
was off for 3 days" by checking freshness on every cycle.

2. PRODUCTION STRATEGY (future migration)
-----------------------------------------
Replace this with Celery Beat + a Celery task. Schedule template:

    "youtube-sync-every-6h": {
        "task": "app.tasks.youtube_sync.run",
        "schedule": crontab(hour="*/6"),
    }

The Celery task body is identical to `_sync_all()` below. Same DB writes,
same error isolation. Only the trigger mechanism changes.

Why Celery in production: multiple FastAPI replicas → multiple in-process
schedulers → duplicate API calls and double-counting. Celery Beat as a
single dedicated process ensures exactly-once scheduling.

To gate this scheduler from production, wrap the lifespan call:

    if settings.app_env != "production":
        start_insights_scheduler()
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.db import async_session as async_session_factory
from app.insights.sync import sync_connection
from app.models.social_connection import SocialConnection

logger = logging.getLogger(__name__)


# ─── Tunable parameters ────────────────────────────────────────

INTERVAL_HOURS = 6                  # how often the loop wakes
FRESHNESS_THRESHOLD_HOURS = 5       # sync if last_synced > this many hours ago
STARTUP_DELAY_SECONDS = 10          # wait for FastAPI to settle before first run
PER_CONNECTION_DELAY_SECONDS = 2    # be polite to YouTube between calls


# ─── Internal state ────────────────────────────────────────────

_scheduler_task: asyncio.Task | None = None


# ─── Sync runner ───────────────────────────────────────────────

async def _sync_all() -> dict[str, int]:
    """
    Run sync on every connection that needs it.

    Returns a summary: {"ok": N, "failed": N, "skipped": N}
    """
    summary = {"ok": 0, "failed": 0, "skipped": 0}

    async with async_session_factory() as session:
        # Pull all youtube connections; we'll filter in Python by freshness
        stmt = (
            select(SocialConnection)
            .where(SocialConnection.platform == "youtube")
        )
        connections = (await session.execute(stmt)).scalars().all()

    if not connections:
        logger.info("[insights.scheduler] no youtube connections to sync")
        return summary

    threshold = datetime.now(timezone.utc) - timedelta(
        hours=FRESHNESS_THRESHOLD_HOURS,
    )

    for i, connection in enumerate(connections):
        # Stagger between calls — don't burst-spam YouTube
        if i > 0:
            await asyncio.sleep(PER_CONNECTION_DELAY_SECONDS)

        # Skip connections that synced recently
        if (
            connection.last_synced_at
            and connection.last_synced_at > threshold
        ):
            logger.debug(
                "[insights.scheduler] %s: synced %s ago, skipping",
                connection.handle or connection.platform_user_id,
                _humanize_age(connection.last_synced_at),
            )
            summary["skipped"] += 1
            continue

        try:
            # Each sync gets its own session so DB issues are isolated
            async with async_session_factory() as session:
                await sync_connection(connection.id, session)
            summary["ok"] += 1
        except Exception as exc:
            # sync_connection already logged + recorded the error;
            # we just count it here and keep going.
            summary["failed"] += 1
            logger.warning(
                "[insights.scheduler] %s sync failed: %s",
                connection.id, str(exc)[:120],
            )

    logger.info(
        "[insights.scheduler] cycle complete: ok=%d failed=%d skipped=%d",
        summary["ok"], summary["failed"], summary["skipped"],
    )
    return summary


# ─── Background loop ───────────────────────────────────────────

async def _scheduler_loop() -> None:
    """
    Long-running background task. Wakes every INTERVAL_HOURS, syncs all
    connections, sleeps. Survives any single-cycle failure.
    """
    await asyncio.sleep(STARTUP_DELAY_SECONDS)
    logger.info("[insights.scheduler] background loop started")

    while True:
        try:
            await _sync_all()
        except Exception as exc:
            # Catch-all so the loop never dies. Individual sync failures
            # are already caught inside _sync_all; this catches anything
            # the inner code missed.
            logger.exception(
                "[insights.scheduler] cycle crashed (continuing): %s", exc,
            )

        sleep_seconds = INTERVAL_HOURS * 3600
        next_run = datetime.now(timezone.utc) + timedelta(seconds=sleep_seconds)
        logger.info(
            "[insights.scheduler] next cycle at %s",
            next_run.strftime("%Y-%m-%d %H:%M UTC"),
        )
        await asyncio.sleep(sleep_seconds)


# ─── Public lifespan helpers ───────────────────────────────────

def start_scheduler() -> None:
    """Spawn the scheduler. Idempotent. Call from FastAPI lifespan startup."""
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        logger.debug("[insights.scheduler] already running")
        return

    loop = asyncio.get_event_loop()
    _scheduler_task = loop.create_task(_scheduler_loop())
    logger.info("[insights.scheduler] spawned background task")


async def stop_scheduler() -> None:
    """Cancel the scheduler. Call from FastAPI shutdown."""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        return

    _scheduler_task.cancel()
    try:
        await _scheduler_task
    except asyncio.CancelledError:
        pass
    logger.info("[insights.scheduler] stopped")


# ─── Helpers ───────────────────────────────────────────────────

def _humanize_age(dt: datetime) -> str:
    """Format a past datetime as '3.2h' for log readability."""
    age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    return f"{age_hours:.1f}h"