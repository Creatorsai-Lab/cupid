"""
Celery task — runs trends ingestion on a schedule.

Schedule via Celery Beat. Add to your celery_app config:

    from celery.schedules import crontab

    celery_app.conf.beat_schedule = {
        "trends-ingest-every-30-min": {
            "task": "app.tasks.trends_ingest.run_ingest",
            "schedule": crontab(minute="*/30"),
        },
    }
"""
from __future__ import annotations

import asyncio
import logging

from app.celery_app import celery_app           # adjust to your Celery instance
from app.trends.ingest import ingest_all_categories

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.trends_ingest.run_ingest")
def run_ingest() -> dict:
    """
    Sync entry point Celery calls. Bridges to async ingestion via asyncio.run.

    Returns: summary dict {category: new_articles_count}
    """
    try:
        return asyncio.run(ingest_all_categories())
    except Exception as exc:
        logger.error("[trends.task] ingestion crashed: %s", exc, exc_info=True)
        return {"error": str(exc)}