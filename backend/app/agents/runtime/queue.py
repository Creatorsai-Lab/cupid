"""Queuing runs for the worker. Imported by the API and the worker; no side
effects on import (unlike worker.py, which selects the event loop).

The queue is SAQ on Postgres, not Redis. SAQ's Redis backend can hand a job out
twice: its sweep re-queues a job caught between being taken off the queue and
being marked active. On Postgres, taking a job and marking it active is one
statement, the sweep only touches jobs past their timeout, and group_key = run
id means a run never has two active jobs.
"""

import time

from saq import Job, Queue
from saq.queue.postgres import PostgresQueue

from app.agents.models import CreatorProfile, RunRequest
from app.agents.runtime.runner import RUN_TIMEOUT_S
from app.config import settings
from app.core.db import psycopg_url

QUEUE_NAME = "agent-runs"
# Backstop only: execute() fails the run at RUN_TIMEOUT_S itself. SAQ's own timeout
# retries the job, which could pay for the stuck step again.
JOB_TIMEOUT_S = RUN_TIMEOUT_S + 60
# Attempts in total, the first included. A crashed worker's job is re-delivered
# after JOB_TIMEOUT_S, and execute() resumes it from its last checkpoint.
JOB_RETRIES = 3
POOL_MAX = 5  # connections per process (API or worker); hosted Postgres limits them


def make_queue(
    database_url: str = settings.database_url, name: str = QUEUE_NAME
) -> PostgresQueue:
    """Not connected yet: the worker's CLI and the API's startup call connect()."""
    return PostgresQueue.from_url(
        psycopg_url(database_url), name=name, min_size=1, max_size=POOL_MAX
    )


async def enqueue_run(
    queue: Queue,
    run_id: str,
    request: RunRequest | None = None,
    *,
    profile: CreatorProfile | None = None,
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
            "profile": profile.model_dump(mode="json") if profile else None,
            "auto_resumes": auto_resumes,
        },
        key=f"{run_id}:{attempt}",
        group_key=run_id,  # one active job per run
        timeout=JOB_TIMEOUT_S,
        retries=JOB_RETRIES,
        scheduled=int(time.time() + delay_s) if delay_s > 0 else 0,
    )
    return await queue.enqueue(job) is not None
