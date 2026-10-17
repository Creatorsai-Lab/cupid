"""End to end with real services: SAQ worker, Redis, Postgres, checkpoints.

A run hits a provider rate limit, the worker queues its own automatic resume
from inside the running job, and the run completes without repeating steps.
"""

import asyncio
import time
import uuid
from contextlib import AsyncExitStack

from redis.asyncio import Redis
from saq import Worker
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agents.graph import PLACEHOLDER_STEPS
from app.agents.llm.errors import RateLimitedError
from app.agents.runtime import worker
from app.agents.runtime.checkpoint import open_checkpointer
from app.agents.runtime.events import EventStream, stream_key
from app.agents.runtime.queue import enqueue_run, make_queue
from app.agents.runtime.runs import RunStore
from app.auth.models import User
from tests.agents.test_contracts import make_request
from tests.agents.test_graph import Calls, steps
from tests.factories import make_user


async def wait_for_status(store: RunStore, run_id: str, status: str, timeout_s: float):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        run = await store.get(run_id)
        if run is not None and run.status == status:
            return
        await asyncio.sleep(0.1)
    run = await store.get(run_id)
    raise AssertionError(
        f"run never reached {status!r}; last status: {run and run.status}"
    )


async def test_quota_failure_resumes_automatically_and_completes(
    engine, test_database_url, real_redis_url, monkeypatch
):
    monkeypatch.setattr(worker, "AUTO_RESUME_DELAYS_S", (0,))  # resume immediately
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user = make_user()
    async with sessions() as session:  # committed: the worker uses its own connections
        session.add(user)
        await session.commit()

    run_id = str(uuid.uuid4())
    store = RunStore(sessions)
    request = make_request(run_id=run_id, user_id=str(user.id))
    await store.create(request)
    queue = make_queue(real_redis_url, name=f"test-{uuid.uuid4().hex[:8]}")
    calls = Calls()
    throttled_once = calls.track(
        "research", PLACEHOLDER_STEPS.research, fail_times=1, error=RateLimitedError
    )
    stack = AsyncExitStack()

    async def startup(ctx):
        runtime, runs = await worker.create_runtime(
            stack,
            database_url=test_database_url,
            redis_url=real_redis_url,
            steps=steps(calls, research=throttled_once),
        )
        ctx.update(runtime=runtime, runs=runs)

    redis = Redis.from_url(real_redis_url, decode_responses=True)
    try:
        assert await enqueue_run(queue, run_id, request)
        # Wait for the outcome, not a timer: a burst worker stops when no job arrives
        # within its timeout and cancels anything still running (flaky when slow).
        saq_worker = Worker(
            queue, [worker.run_pipeline], startup=startup, concurrency=1
        )
        running = asyncio.create_task(saq_worker.start())
        try:
            await wait_for_status(store, run_id, "completed", timeout_s=30)
        finally:
            await saq_worker.stop()
            await running
            await stack.aclose()

        assert calls.count == {"supervisor": 1, "research": 2, "studio": 1}
        types = [e.type for _, e in await EventStream(redis).read(run_id)]
        assert types.count("run.started") == 2  # first attempt + automatic resume
        assert "run.failed" in types and types[-1] == "run.completed"
    finally:
        await redis.delete(stream_key(run_id))
        await redis.aclose()
        await queue.disconnect()
        async with open_checkpointer(test_database_url) as saver:
            await saver.adelete_thread(run_id)
        async with sessions() as session:  # cascades to agent_runs
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()
