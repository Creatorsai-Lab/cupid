"""End to end with real services: SAQ worker, Postgres (queue, runs,
checkpoints) and Redis (events), using the worker's production settings.

- A run hits a provider rate limit, the worker queues its own automatic resume
  from inside the running job, and the run completes without repeating steps.
  The start job is also delivered twice: the copy does nothing.
- A deploy stops the worker mid-step: the running job finishes first.
"""

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, cast

import pytest
from redis.asyncio import Redis
from saq import Worker
from saq.queue.postgres import PostgresQueue
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agents.graph import PLACEHOLDER_STEPS, Steps
from app.agents.llm.errors import RateLimitedError
from app.agents.llm.gateway import RedisCooldowns
from app.agents.llm.roles import ProviderSpec
from app.agents.models import RunRequest
from app.agents.runtime import worker
from app.agents.runtime.checkpoint import open_checkpointer
from app.agents.runtime.events import EventStream, stream_key
from app.agents.runtime.queue import enqueue_run, make_queue
from app.agents.runtime.runs import RunStore
from app.auth.models import User
from tests.agents.test_contracts import make_request
from tests.agents.test_graph import Calls, steps
from tests.factories import make_user

# stop() waits for idle job slots and upkeep sleeps; shorter here, so tests are fast
FAST = {"dequeue_timeout": 1, "timers": {"sweep": 1, "worker_info": 1}}


@dataclass
class Services:
    database_url: str
    redis_url: str
    store: RunStore
    queue: PostgresQueue
    redis: Redis
    run_ids: list[str] = field(default_factory=list)
    user_ids: list[uuid.UUID] = field(default_factory=list)

    async def new_run(self) -> tuple[str, RunRequest]:
        """A user and a queued run, committed: the worker uses its own connections."""
        user = make_user()
        async with self.store._sessions() as session:
            session.add(user)
            await session.commit()
        run_id = str(uuid.uuid4())
        request = make_request(run_id=run_id, user_id=str(user.id))
        await self.store.create(request)
        self.run_ids.append(run_id)
        self.user_ids.append(user.id)
        return run_id, request

    async def event_types(self, run_id: str) -> list[str]:
        return [e.type for _, e in await EventStream(self.redis).read(run_id)]


@pytest.fixture
async def services(engine, test_database_url, real_redis_url):
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    queue = make_queue(test_database_url, name=f"test-{uuid.uuid4().hex[:8]}")
    await queue.connect()
    redis = Redis.from_url(real_redis_url, decode_responses=True)
    svc = Services(test_database_url, real_redis_url, RunStore(sessions), queue, redis)
    yield svc
    for run_id in svc.run_ids:
        await redis.delete(stream_key(run_id))
    await redis.aclose()
    async with queue.pool.connection() as conn:
        await conn.execute("DELETE FROM saq_jobs WHERE queue = %s", [queue.name])
    await queue.disconnect()
    async with open_checkpointer(test_database_url) as saver:
        for run_id in svc.run_ids:
            await saver.adelete_thread(run_id)
    async with sessions() as session:  # cascades to agent_runs
        await session.execute(delete(User).where(User.id.in_(svc.user_ids)))
        await session.commit()


@asynccontextmanager
async def running_worker(svc: Services, pipeline: Steps) -> AsyncIterator[Worker]:
    """The production worker settings with the test's queue, services and steps."""

    async def startup(ctx):
        stack = AsyncExitStack()
        runtime, runs = await worker.create_runtime(
            stack,
            database_url=svc.database_url,
            redis_url=svc.redis_url,
            providers={},
            build_steps=lambda _: pipeline,
        )
        ctx.update(runtime=runtime, runs=runs, stack=stack)

    settings = worker.worker_settings | FAST | {"queue": svc.queue, "startup": startup}
    saq_worker = Worker(**cast(dict[str, Any], settings))
    started = asyncio.create_task(saq_worker.start())
    try:
        yield saq_worker
    finally:
        await saq_worker.stop()
        await started


async def wait_until_settled(svc: Services, run_id: str) -> None:
    """Wait for the outcome, not a timer: the run finished and no job is left."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        run = await svc.store.get(run_id)
        if run is not None and run.status == "completed":
            if await svc.queue.count("incomplete") == 0:
                return
        await asyncio.sleep(0.1)
    run = await svc.store.get(run_id)
    raise AssertionError(f"not settled; run status: {run and run.status}")


async def test_quota_failure_resumes_automatically_and_completes(services, monkeypatch):
    monkeypatch.setattr(worker, "AUTO_RESUME_DELAYS_S", (0,))  # resume immediately
    calls = Calls()
    throttled_once = calls.track(
        "research", PLACEHOLDER_STEPS.research, fail_times=1, error=RateLimitedError
    )
    run_id, request = await services.new_run()
    assert await enqueue_run(services.queue, run_id, request)
    assert await enqueue_run(services.queue, run_id, request, attempt="delivered-twice")

    async with running_worker(services, steps(calls, research=throttled_once)):
        await wait_until_settled(services, run_id)

    assert calls.count == {"supervisor": 1, "research": 2, "studio": 1}
    types = await services.event_types(run_id)
    assert types.count("run.started") == 2  # first attempt + one resume, no copies
    assert "run.failed" in types and types[-1] == "run.completed"


async def test_deploy_lets_the_running_job_finish(services):
    in_studio = asyncio.Event()

    async def slow_studio(state):
        in_studio.set()
        await asyncio.sleep(1)
        return await PLACEHOLDER_STEPS.studio(state)

    calls = Calls()
    run_id, request = await services.new_run()
    assert await enqueue_run(services.queue, run_id, request)

    pipeline = steps(calls, studio=calls.track("studio", slow_studio))
    async with running_worker(services, pipeline) as saq_worker:
        await asyncio.wait_for(in_studio.wait(), 30)
        await saq_worker.stop()  # a deploy, mid-step

    run = await services.store.get(run_id)
    assert run is not None and run.status == "completed"
    assert calls.count == {"supervisor": 1, "research": 1, "studio": 1}
    assert (await services.event_types(run_id)).count("run.started") == 1


async def test_steps_share_the_workers_llm_gateway_and_http_client(services):
    built: list[worker.Services] = []

    def build_steps(shared: worker.Services) -> Steps:
        built.append(shared)
        return PLACEHOLDER_STEPS

    # A provider that is listed but never called: this test makes no LLM requests.
    providers = {"groq": ProviderSpec("groq", "https://llm.invalid", "model", "key")}
    try:
        async with AsyncExitStack() as stack:
            await worker.create_runtime(
                stack,
                database_url=services.database_url,
                redis_url=services.redis_url,
                providers=providers,
                build_steps=build_steps,
            )
            [shared] = built  # built exactly once, at startup
            assert [
                p.name for p in await shared.llm.candidates("research_planning", None)
            ] == ["groq"]

            # A rate limit seen by any worker pauses the provider for all of them.
            await RedisCooldowns(services.redis).start("groq", 30)
            assert await shared.llm.candidates("research_planning", None) == []
            assert not shared.http.is_closed

        assert shared.http.is_closed  # closed when the worker shuts down
    finally:
        await services.redis.delete(RedisCooldowns.key("groq"))
