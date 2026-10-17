"""The runner: one function that starts or resumes a run, reports progress as
events, and records the outcome, and ignores duplicate jobs (SAQ can deliver a
job twice). Uses the placeholder pipeline, an in-memory checkpointer, an
in-memory Redis and an in-memory run store."""

import asyncio

import pytest
from fakeredis import FakeAsyncRedis
from langgraph.checkpoint.memory import InMemorySaver

from app.agents.graph import PLACEHOLDER_STEPS, build_graph
from app.agents.llm.errors import RateLimitedError
from app.agents.models import Issue
from app.agents.runtime.checkpoint import checkpoint_serde
from app.agents.runtime.events import EventStream
from app.agents.runtime.runner import USER_ERROR, Runtime, execute
from tests.agents.test_contracts import make_request
from tests.agents.test_graph import Calls, steps
from tests.fakes import FakeRuns

RUN_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
async def redis():
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()


def runtime(
    redis, calls: Calls | None = None, runs: FakeRuns | None = None, **step_overrides
) -> Runtime:
    graph = build_graph(
        steps(calls or Calls(), **step_overrides),
        checkpointer=InMemorySaver(serde=checkpoint_serde()),
    )
    return Runtime(graph=graph, events=EventStream(redis), runs=runs or FakeRuns())


def runs_of(rt: Runtime) -> FakeRuns:
    assert isinstance(rt.runs, FakeRuns)
    return rt.runs


async def event_types(rt: Runtime) -> list[str]:
    return [e.type for _, e in await rt.events.read(RUN_ID)]


async def test_completed_run_reports_every_step_in_order(redis):
    rt = runtime(redis)

    status = (await execute(rt, RUN_ID, make_request(run_id=RUN_ID))).status

    assert status == "completed"
    assert await event_types(rt) == [
        "run.started",
        "step.started",
        "step.finished",  # supervisor
        "step.started",
        "research.sources",
        "step.finished",  # research
        "step.started",
        "piece.ready",
        "step.finished",  # studio
        "run.completed",
    ]
    assert runs_of(rt).history == [("running", None), ("completed", None)]


async def test_piece_events_carry_the_content(redis):
    rt = runtime(redis)
    await execute(rt, RUN_ID, make_request(run_id=RUN_ID))

    pieces = [e for _, e in await rt.events.read(RUN_ID) if e.type == "piece.ready"]

    assert pieces[0].data["deliverable"] == "linkedin_post"
    assert pieces[0].data["blocks"][0]["text"].startswith("[Placeholder draft]")


async def test_blocked_run_tells_the_user_why(redis):
    rt = runtime(redis)

    status = (
        await execute(rt, RUN_ID, make_request(run_id=RUN_ID, prompt="  "))
    ).status

    assert status == "blocked"
    last = (await rt.events.read(RUN_ID))[-1][1]
    assert (last.type, last.data["reason"]) == (
        "run.blocked",
        "Please describe what you want to create.",
    )
    assert runs_of(rt).history[-1] == ("blocked", None)


async def test_issues_make_a_degraded_run(redis):
    async def research_with_issue(state):
        update = await PLACEHOLDER_STEPS.research(state)
        issue = Issue(step="research", severity="degraded", message="Few sources")
        return update | {"issues": [issue]}

    rt = runtime(redis, research=research_with_issue)

    status = (await execute(rt, RUN_ID, make_request(run_id=RUN_ID))).status

    assert status == "degraded"
    last = (await rt.events.read(RUN_ID))[-1][1]
    assert last.type == "run.degraded"
    assert last.data["issues"] == [
        {"step": "research", "severity": "degraded", "message": "Few sources"}
    ]
    assert last.data["research"] == "skipped"


async def test_failure_shows_a_safe_message_and_resume_finishes_the_run(redis):
    calls = Calls()
    crashing = calls.track("research", PLACEHOLDER_STEPS.research, fail_times=1)
    rt = runtime(redis, calls, research=crashing)

    assert (await execute(rt, RUN_ID, make_request(run_id=RUN_ID))).status == "failed"
    failed = (await rt.events.read(RUN_ID))[-1][1]
    assert failed.type == "run.failed"
    assert failed.data == {"message": USER_ERROR, "resume_later": False}
    assert "crashed" not in str(
        runs_of(rt).history
    )  # internal details stay in the logs

    assert await runs_of(rt).claim_for_resume(
        RUN_ID, None
    )  # as the resume endpoint does
    assert (await execute(rt, RUN_ID)).status == "completed"  # resume: no request
    assert calls.count == {"supervisor": 1, "research": 2, "studio": 1}
    assert (await rt.events.read(RUN_ID))[-1][1].type == "run.completed"


async def test_quota_failures_are_flagged_for_automatic_resume(redis):
    calls = Calls()
    throttled = calls.track(
        "research", PLACEHOLDER_STEPS.research, fail_times=1, error=RateLimitedError
    )
    rt = runtime(redis, calls, research=throttled)

    outcome = await execute(rt, RUN_ID, make_request(run_id=RUN_ID))
    assert (outcome.status, outcome.resume_later) == ("failed", True)
    assert (await rt.events.read(RUN_ID))[-1][1].data["resume_later"] is True


async def test_resuming_an_unknown_run_fails_cleanly(redis):
    rt = runtime(redis)

    assert (await execute(rt, RUN_ID)).status == "failed"
    assert (await rt.events.read(RUN_ID))[-1][1].type == "run.failed"


async def test_job_redelivered_after_the_worker_died_resumes_where_it_stopped(redis):
    """The worker dies mid-step (its task is cancelled): the run stays "running"
    with its checkpoints; SAQ delivers the start job again; done steps don't repeat."""
    in_research = asyncio.Event()

    async def hangs_once(state):
        if not in_research.is_set():
            in_research.set()
            await asyncio.Event().wait()  # until the worker dies
        return await PLACEHOLDER_STEPS.research(state)

    calls = Calls()
    rt = runtime(redis, calls, research=calls.track("research", hangs_once))
    request = make_request(run_id=RUN_ID)

    job = asyncio.create_task(execute(rt, RUN_ID, request))
    await in_research.wait()
    job.cancel()
    with pytest.raises(asyncio.CancelledError):
        await job
    assert runs_of(rt).status == "running"

    outcome = await execute(rt, RUN_ID, request)  # same start job delivered again

    assert outcome.status == "completed"
    assert calls.count == {"supervisor": 1, "research": 2, "studio": 1}


async def test_duplicate_job_does_nothing_while_the_run_executes_elsewhere(redis):
    calls = Calls()
    rt = runtime(redis, calls, runs=FakeRuns(held_elsewhere=True))

    outcome = await execute(rt, RUN_ID, make_request(run_id=RUN_ID))

    assert outcome.status == "skipped"
    assert (calls.count, await event_types(rt), runs_of(rt).history) == ({}, [], [])


@pytest.mark.parametrize("status", ["completed", "degraded", "blocked", "failed"])
async def test_stale_job_for_a_finished_run_does_nothing(redis, status):
    """Only queued runs (or runs whose worker died) execute; a failed run must be
    claimed for resume first, so a leftover job can't resume it behind the user."""
    calls = Calls()
    rt = runtime(redis, calls, runs=FakeRuns(status=status))

    outcome = await execute(rt, RUN_ID, make_request(run_id=RUN_ID))

    assert outcome.status == "skipped"
    assert (calls.count, await event_types(rt), runs_of(rt).history) == ({}, [], [])
