"""
Trends Scheduler — drift-tolerant background ingestion.

Based on principle: "scheduled invocation with idempotency"

DEV STRATEGY (this file)
------------------------
We run a single asyncio task inside FastAPI's lifespan. On startup it:
    1. Checks the DB for the freshest article timestamp
    2. If data is staler than `freshness_threshold_hours`, runs ingestion now
    3. Sleeps for `interval_hours`, then loops back to step 1

This handles the "my laptop was off for a week" scenario cleanly:
    - Open laptop → FastAPI starts → DB says "last article 5 days old"
    - Threshold is 36h, so we exceed it → ingestion runs immediately
    - Loop sleeps for 48h → wakes up → still fresh? skip. Stale? fetch.

Single process. No Celery. No Redis broker. No Windows quirks.

PRODUCTION STRATEGY (future migration)
--------------------------------------
For production, you DO NOT use this scheduler. Replace with Celery Beat:

    1. Move `ingest_all_categories()` call into a Celery task
       (already has a stub at app/tasks/trends_ingest.py)

    2. In your celery_app.py beat_schedule:
           "trends-ingest-every-2-days": {
               "task": "app.tasks.trends_ingest.run_ingest",
               "schedule": crontab(hour=3, minute=0, day_of_month="*/2"),
           }

    3. Run three processes:
           - uvicorn (web)
           - celery worker (executor)
           - celery beat (scheduler)

    4. Disable this scheduler by gating the lifespan call on settings:
           if settings.environment != "production":
               start_trends_scheduler(app)

Why Celery in production but not dev?
    - Production runs 24/7, so the "laptop off" problem doesn't exist
    - Multiple FastAPI replicas (load-balanced) would each spawn their own
      scheduler → duplicate fetches and duplicate writes
    - Celery Beat runs as a single dedicated process, ensuring exactly-once
      scheduling regardless of how many web replicas you have
    - Failures are observable (Flower dashboard, retries, dead-letter queues)

The CORE LOGIC stays identical. Both dev and prod call the same
`ingest_all_categories()` function. We swap only HOW it's invoked.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session as async_session_factory
from app.models.trending_article import TrendingArticle
from app.trends.ingest import ingest_all_categories

logger = logging.getLogger(__name__)


# ─── Tunable parameters ────────────────────────────────────────
# Keep these as module constants for easy tuning. In a real product
# you'd put these in app/config.py as Settings fields.

INTERVAL_HOURS = 48                  # how often the loop wakes
FRESHNESS_THRESHOLD_HOURS = 36       # stale if no articles within this window
STARTUP_DELAY_SECONDS = 5            # let FastAPI finish booting before we touch DB


# ─── DB freshness check ────────────────────────────────────────

async def _hours_since_last_article(session: AsyncSession) -> float | None:
    """
    Return how many hours have passed since the freshest article was
    ingested. Returns None if the table is completely empty.

    Why ingested_at and not published_at?
        published_at = when the publisher posted it (could be old)
        ingested_at  = when WE pulled it into our DB
    We care about ingestion freshness — that's our control surface.
    """
    stmt = select(func.max(TrendingArticle.ingested_at))
    result = await session.execute(stmt)
    latest = result.scalar()

    if latest is None:
        return None

    # Make sure both datetimes are timezone-aware
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)

    delta = datetime.now(timezone.utc) - latest
    return delta.total_seconds() / 3600


async def _is_stale() -> bool:
    """True if data is older than the freshness threshold (or empty)."""
    async with async_session_factory() as session:
        hours = await _hours_since_last_article(session)

    if hours is None:
        logger.info("[trends.scheduler] DB is empty, scheduling immediate ingestion")
        return True

    is_stale = hours >= FRESHNESS_THRESHOLD_HOURS
    logger.info(
        "[trends.scheduler] last ingest %.1fh ago (threshold %dh) -> %s",
        hours, FRESHNESS_THRESHOLD_HOURS,
        "STALE, will fetch" if is_stale else "fresh, skipping",
    )
    return is_stale


# ─── Background loop ───────────────────────────────────────────

async def _scheduler_loop() -> None:
    """
    Long-running background task. Wakes every INTERVAL_HOURS, ingests
    if data is stale.

    Designed to never crash the loop on a single failure — any exception
    in `ingest_all_categories` is logged and we sleep until the next cycle.
    """
    # Small delay so FastAPI's startup logs aren't drowned out
    await asyncio.sleep(STARTUP_DELAY_SECONDS)

    logger.info("[trends.scheduler] background loop started")

    while True:
        try:
            if await _is_stale():
                logger.info("[trends.scheduler] running ingestion...")
                summary = await ingest_all_categories()
                total = sum(summary.values())
                logger.info("[trends.scheduler] cycle complete, %d new articles", total)
        except Exception as exc:
            # Log and keep going — never let one bad cycle kill the loop
            logger.exception("[trends.scheduler] cycle failed: %s", exc)

        # Sleep until the next check
        sleep_seconds = INTERVAL_HOURS * 3600
        next_run = datetime.now(timezone.utc) + timedelta(seconds=sleep_seconds)
        logger.info(
            "[trends.scheduler] next check at %s",
            next_run.strftime("%Y-%m-%d %H:%M UTC"),
        )
        await asyncio.sleep(sleep_seconds)


# ─── Public lifespan helper ────────────────────────────────────

_scheduler_task: asyncio.Task | None = None


def start_scheduler() -> None:
    """
    Spawn the scheduler as a background task. Call from FastAPI lifespan.

    Idempotent — calling twice (e.g., during reload) won't spawn duplicates.
    """
    global _scheduler_task

    if _scheduler_task is not None and not _scheduler_task.done():
        logger.debug("[trends.scheduler] already running, skipping spawn")
        return

    loop = asyncio.get_event_loop()
    _scheduler_task = loop.create_task(_scheduler_loop())
    logger.info("[trends.scheduler] spawned background task")


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
    logger.info("[trends.scheduler] stopped")


# ─── Optional: lifespan context manager ────────────────────────

@asynccontextmanager
async def trends_lifespan(app: FastAPI):
    """
    FastAPI lifespan integration.

    Usage in main.py:
        from app.trends.scheduler import trends_lifespan
        app = FastAPI(lifespan=trends_lifespan)

    Or, if you already have a lifespan, call start_scheduler/stop_scheduler
    inside your existing one.
    """
    start_scheduler()
    yield
    await stop_scheduler()