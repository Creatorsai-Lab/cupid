"""Background worker: runs agent pipelines outside the API process (SAQ; the
queue lives in Postgres, see queue.py).

Start it from backend/ (one terminal per worker):

    uv run saq app.agents.runtime.worker.worker_settings

A deploy lets running jobs finish (up to SHUTDOWN_GRACE_S); the hosting
platform's stop timeout must be longer. A crash never loses a run: SAQ
re-delivers the job and execute() resumes from the last checkpoint. Runs that
failed on provider quota are resumed automatically after a delay, a limited
number of times.

Duplicate jobs are harmless: SAQ can deliver a job twice, so execute() runs a
run only while holding its database lock, and only if it's queued (runner.py).
Resumes are claimed in the database (RunStore.claim_for_resume), not by SAQ
keys: SAQ refuses a key while a job with it is in flight, and the automatic
resume is enqueued from inside the run's own job.
"""

import asyncio
import logging
import sys
from collections.abc import Sequence
from contextlib import AsyncExitStack
from typing import Any, Required

if sys.platform == "win32":
    # psycopg (Postgres checkpoints) can't use Windows' default Proactor loop.
    # SAQ imports this module before it creates its event loop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from redis.asyncio import Redis
from saq.types import Context
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.graph import PLACEHOLDER_STEPS, Steps, build_graph
from app.agents.models import RunRequest
from app.agents.runtime.checkpoint import open_checkpointer
from app.agents.runtime.events import EventStream
from app.agents.runtime.queue import enqueue_run, make_queue
from app.agents.runtime.runner import Runtime, execute
from app.agents.runtime.runs import RunStore
from app.config import settings

logger = logging.getLogger("app.agents.worker")


class WorkerContext(Context, total=False):
    """SAQ's job context plus what startup() puts in it (present for every job)."""

    runtime: Required[Runtime]
    runs: Required[RunStore]
    stack: Required[AsyncExitStack]


CONCURRENCY = 2  # free-tier LLM quota is the bottleneck, not CPU
SHUTDOWN_GRACE_S = 300  # on stop, running jobs get this long to finish
# A stopping worker waits for its idle job slots (they wake this often; a job that
# arrives meanwhile still runs, within the grace period) and for its upkeep loops'
# sleeps, so both stay short.
DEQUEUE_TIMEOUT_S = 5
TIMERS = {"sweep": 10, "worker_info": 10}
AUTO_RESUME_DELAYS_S: Sequence[float] = (60, 120, 300)  # one per automatic resume


async def run_pipeline(
    ctx: WorkerContext,
    *,
    run_id: str,
    request: dict[str, Any] | None = None,
    auto_resumes: int = 0,
) -> str:
    """The SAQ job: run (or resume) the pipeline; schedule a resume after quota errors."""
    runtime: Runtime = ctx["runtime"]
    runs: RunStore = ctx["runs"]
    outcome = await execute(
        runtime, run_id, RunRequest.model_validate(request) if request else None
    )
    if outcome.resume_later and auto_resumes < len(AUTO_RESUME_DELAYS_S):
        if await runs.claim_for_resume(run_id, None):
            queued = await enqueue_run(
                ctx["worker"].queue,
                run_id,
                attempt=f"auto-{auto_resumes + 1}",
                delay_s=AUTO_RESUME_DELAYS_S[auto_resumes],
                auto_resumes=auto_resumes + 1,
            )
            if not queued:  # never leave a run stuck as "queued"
                logger.error("run %s: automatic resume could not be queued", run_id)
                await runs.set_status(run_id, "failed")
    return outcome.status


async def create_runtime(
    stack: AsyncExitStack,
    *,
    database_url: str,
    redis_url: str,
    steps: Steps = PLACEHOLDER_STEPS,
) -> tuple[Runtime, RunStore]:
    """Everything a worker needs; closed by `stack` on shutdown."""
    redis = Redis.from_url(redis_url, decode_responses=True)
    stack.push_async_callback(redis.aclose)
    engine = create_async_engine(database_url, pool_pre_ping=True)
    stack.push_async_callback(engine.dispose)
    runs = RunStore(async_sessionmaker(engine, expire_on_commit=False))
    saver = await stack.enter_async_context(open_checkpointer(database_url))
    graph = build_graph(steps, checkpointer=saver)
    return Runtime(graph=graph, events=EventStream(redis), runs=runs), runs


async def startup(ctx: WorkerContext) -> None:
    stack = AsyncExitStack()
    runtime, runs = await create_runtime(
        stack, database_url=settings.database_url, redis_url=settings.redis_url
    )
    ctx.update(stack=stack, runtime=runtime, runs=runs)


async def shutdown(ctx: WorkerContext) -> None:
    await ctx["stack"].aclose()


worker_settings = {
    "queue": make_queue(),
    "functions": [run_pipeline],
    "concurrency": CONCURRENCY,
    "startup": startup,
    "shutdown": shutdown,
    "shutdown_grace_period_s": SHUTDOWN_GRACE_S,
    "dequeue_timeout": DEQUEUE_TIMEOUT_S,
    "timers": TIMERS,
}
