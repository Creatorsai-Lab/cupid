"""Queuing runs for the worker. Imported by the API and the worker; no side
effects on import (unlike worker.py, which selects the event loop)."""

import time

from saq import Job, Queue

from app.agents.models import RunRequest
from app.config import settings

QUEUE_NAME = "agent-runs"
JOB_TIMEOUT_S = 15 * 60  # a stuck run is aborted and re-delivered after this
JOB_RETRIES = 2  # re-deliveries after a crash or timeout; execute() resumes


def make_queue(redis_url: str = settings.redis_url, name: str = QUEUE_NAME) -> Queue:
    return Queue.from_url(redis_url, name=name)


async def enqueue_run(
    queue: Queue,
    run_id: str,
    request: RunRequest | None = None,
    *,
    attempt: str = "start",
    delay_s: float = 0,
    auto_resumes: int = 0,
) -> bool:
    """Queue one attempt of a run. False if that exact attempt is already queued."""
    job = Job(
        function="run_pipeline",
        kwargs={
            "run_id": run_id,
            "request": request.model_dump(mode="json") if request else None,
            "auto_resumes": auto_resumes,
        },
        key=f"{run_id}:{attempt}",
        timeout=JOB_TIMEOUT_S,
        retries=JOB_RETRIES,
        scheduled=int(time.time() + delay_s) if delay_s > 0 else 0,
    )
    return await queue.enqueue(job) is not None
