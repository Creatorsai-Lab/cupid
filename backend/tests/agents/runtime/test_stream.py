"""The live event stream (SSE): events in order with ids, a clean end after the
final event, continuing after a reconnect, keep-alives while waiting, and a
final event from the run record when the Redis stream has expired."""

from dataclasses import dataclass

import pytest
from fakeredis import FakeAsyncRedis

from app.agents.models import RunEvent
from app.agents.runtime import stream
from app.agents.runtime.events import EventStream

RUN_ID = "33333333-3333-3333-3333-333333333333"


@dataclass
class FakeRun:
    status: str
    error: str | None = None


class FakeRuns:
    def __init__(self, status: str = "running", error: str | None = None) -> None:
        self.run = FakeRun(status, error)

    async def get(self, run_id):
        return self.run


@pytest.fixture
async def events():
    redis = FakeAsyncRedis(decode_responses=True)
    yield EventStream(redis)
    await redis.aclose()


async def never_disconnected() -> bool:
    return False


async def collect(events, runs, after="0-0", limit=20) -> list[str]:
    frames = []
    async for frame in stream.event_stream(
        RUN_ID,
        events=events,
        runs=runs,
        after=after,
        is_disconnected=never_disconnected,
    ):
        frames.append(frame)
        if len(frames) >= limit:
            break
    return frames


async def publish(events, type_: str, **data) -> str:
    return await events.publish(
        RunEvent.model_validate({"run_id": RUN_ID, "type": type_, "data": data})
    )


async def test_events_stream_in_order_and_end_after_the_final_event(events):
    first = await publish(events, "run.started")
    await publish(events, "step.started")
    last = await publish(events, "run.completed", pieces=1)

    frames = await collect(events, FakeRuns())

    assert len(frames) == 3
    assert frames[0].startswith(f"id: {first}\nevent: run.started\ndata: ")
    assert frames[-1].startswith(f"id: {last}\nevent: run.completed\n")
    assert frames[-1].endswith("\n\n")


async def test_reconnect_continues_after_the_last_seen_event(events):
    first = await publish(events, "run.started")
    await publish(events, "run.completed")

    frames = await collect(events, FakeRuns(), after=stream.start_after(first))

    assert [f.split("\n")[1] for f in frames] == ["event: run.completed"]


@pytest.mark.parametrize("header", [None, "", "garbage", "1-2-3", "$"])
def test_invalid_last_event_ids_start_from_the_beginning(header):
    assert stream.start_after(header) == "0-0"


async def test_waiting_sends_keep_alives(events, monkeypatch):
    monkeypatch.setattr(stream, "SSE_BLOCK_MS", 10)
    frames = await collect(events, FakeRuns("running"), limit=2)
    assert frames == [": keep-alive\n\n", ": keep-alive\n\n"]


async def test_expired_stream_of_a_finished_run_ends_with_its_recorded_outcome(events):
    frames = await collect(events, FakeRuns("failed", error="Something went wrong."))

    assert len(frames) == 1
    assert frames[0].startswith("event: run.failed\n")
    assert '"message":"Something went wrong."' in frames[0]


async def test_stream_stops_when_the_client_disconnects(events):
    async def disconnected() -> bool:
        return True

    frames = [
        f
        async for f in stream.event_stream(
            RUN_ID,
            events=events,
            runs=FakeRuns(),
            after="0-0",
            is_disconnected=disconnected,
        )
    ]
    assert frames == []
