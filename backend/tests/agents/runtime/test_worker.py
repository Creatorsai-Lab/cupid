"""Worker job logic with fakes: queuing attempts, and automatic resume after
quota errors (bounded, claimed atomically, never left stuck)."""

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import cast

import pytest
from fakeredis import FakeAsyncRedis
from langgraph.checkpoint.memory import InMemorySaver

from app.agents.graph import PLACEHOLDER_STEPS, build_graph
from app.agents.llm.errors import RateLimitedError
from app.agents.runtime import queue as run_queue
from app.agents.runtime import worker
from app.agents.runtime.checkpoint import checkpoint_serde
from app.agents.runtime.events import EventStream
from app.agents.runtime.runner import Runtime
from tests.agents.test_contracts import make_request
from tests.agents.test_graph import Calls, steps
from tests.fakes import FakeRuns

RUN_ID = "22222222-2222-2222-2222-222222222222"


@dataclass
class FakeQueue:
    jobs: list = field(default_factory=list)
    accept: bool = True

    async def enqueue(self, job):
        if not self.accept:
            return None
        self.jobs.append(job)
        return job


@pytest.fixture
async def redis():
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


def context(
    redis, runs: FakeRuns, queue: FakeQueue, **step_overrides
) -> worker.WorkerContext:
    graph = build_graph(
        steps(Calls(), **step_overrides),
        checkpointer=InMemorySaver(serde=checkpoint_serde()),
    )
    runtime = Runtime(graph=graph, events=EventStream(redis), runs=runs)
    # Fakes stand in for the worker, store and queue: they behave alike, so cast.
    return cast(
        worker.WorkerContext,
        {"runtime": runtime, "runs": runs, "worker": SimpleNamespace(queue=queue)},
    )


def throttled_research():
    calls = Calls()
    return calls.track(
        "research", PLACEHOLDER_STEPS.research, fail_times=99, error=RateLimitedError
    )


async def test_enqueue_builds_one_keyed_attempt():
    queue = FakeQueue()
    request = make_request(run_id=RUN_ID)

    assert await run_queue.enqueue_run(queue, RUN_ID, request)  # type: ignore[arg-type]

    job = queue.jobs[0]
    assert job.function == "run_pipeline"
    assert job.key == f"{RUN_ID}:start"
    assert job.kwargs == {
        "run_id": RUN_ID,
        "request": request.model_dump(mode="json"),
        "auto_resumes": 0,
    }
    assert (job.timeout, job.retries, job.scheduled) == (
        run_queue.JOB_TIMEOUT_S,
        run_queue.JOB_RETRIES,
        0,
    )


async def test_completed_run_queues_nothing(redis):
    runs, queue = FakeRuns(), FakeQueue()
    ctx = context(redis, runs, queue)

    status = await worker.run_pipeline(
        ctx, run_id=RUN_ID, request=make_request(run_id=RUN_ID).model_dump(mode="json")
    )

    assert status == "completed"
    assert (queue.jobs, runs.claims) == ([], 0)


async def test_quota_failure_schedules_an_automatic_resume(redis):
    runs, queue = FakeRuns(), FakeQueue()
    ctx = context(redis, runs, queue, research=throttled_research())

    status = await worker.run_pipeline(
        ctx, run_id=RUN_ID, request=make_request(run_id=RUN_ID).model_dump(mode="json")
    )

    assert status == "failed"
    job = queue.jobs[0]
    assert job.key == f"{RUN_ID}:auto-1"
    assert job.kwargs == {"run_id": RUN_ID, "request": None, "auto_resumes": 1}
    assert job.scheduled > 0  # delayed until the quota recovers


async def test_automatic_resumes_stop_at_the_limit(redis):
    runs, queue = FakeRuns(), FakeQueue()
    ctx = context(redis, runs, queue, research=throttled_research())
    limit = len(worker.AUTO_RESUME_DELAYS_S)

    await worker.run_pipeline(
        ctx,
        run_id=RUN_ID,
        request=make_request(run_id=RUN_ID).model_dump(mode="json"),
        auto_resumes=limit,
    )

    assert (queue.jobs, runs.claims) == ([], 0)


async def test_no_resume_when_another_caller_already_claimed_the_run(redis):
    runs, queue = FakeRuns(claimable=False), FakeQueue()
    ctx = context(redis, runs, queue, research=throttled_research())

    await worker.run_pipeline(
        ctx, run_id=RUN_ID, request=make_request(run_id=RUN_ID).model_dump(mode="json")
    )

    assert queue.jobs == []


async def test_a_resume_that_cannot_be_queued_does_not_leave_the_run_stuck(redis):
    runs, queue = FakeRuns(), FakeQueue(accept=False)
    ctx = context(redis, runs, queue, research=throttled_research())

    await worker.run_pipeline(
        ctx, run_id=RUN_ID, request=make_request(run_id=RUN_ID).model_dump(mode="json")
    )

    assert runs.statuses[-1] == "failed"
