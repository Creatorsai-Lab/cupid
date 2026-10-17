"""Run events on a Redis stream: ordered, resumable from any point (so a browser
reconnect misses nothing), size-bounded and auto-expiring."""

import pytest
from fakeredis import FakeAsyncRedis

from app.agents.models import RunEvent
from app.agents.runtime.events import STREAM_TTL_S, EventStream, stream_key


@pytest.fixture
async def events():
    redis = FakeAsyncRedis(decode_responses=True)
    yield EventStream(redis)
    await redis.aclose()


def event(type_: str, step: str | None = None, **data) -> RunEvent:
    return RunEvent.model_validate(
        {"run_id": "run-1", "type": type_, "step": step, "data": data}
    )


async def test_events_are_read_back_in_order(events):
    for e in (event("run.started"), event("step.started", "supervisor")):
        await events.publish(e)

    read = await events.read("run-1")

    assert [e.type for _, e in read] == ["run.started", "step.started"]
    assert read[1][1].step == "supervisor"


async def test_reading_after_an_id_returns_only_newer_events(events):
    first = await events.publish(event("run.started"))
    await events.publish(event("step.started", "supervisor"))

    read = await events.read("run-1", after=first)

    assert [e.type for _, e in read] == ["step.started"]


async def test_event_data_survives_the_round_trip(events):
    await events.publish(event("run.blocked", reason="Prompt is empty"))
    (_, read), *_ = await events.read("run-1")
    assert read.data == {"reason": "Prompt is empty"}


async def test_streams_expire_and_stay_separate_per_run(events):
    await events.publish(event("run.started"))
    other = RunEvent(run_id="run-2", type="run.started")
    await events.publish(other)

    ttl = await events.redis.ttl(stream_key("run-1"))
    assert 0 < ttl <= STREAM_TTL_S
    assert len(await events.read("run-1")) == 1
    assert len(await events.read("run-2")) == 1


async def test_reading_with_nothing_new_returns_empty(events):
    first = await events.publish(event("run.started"))
    assert await events.read("run-1", after=first, block_ms=10) == []
    assert await events.read("missing-run") == []
