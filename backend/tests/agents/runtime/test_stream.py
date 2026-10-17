"""The live event stream (SSE): events in order with ids, an explicit end once
the run is finished, continuing after a reconnect, keep-alives while waiting, a
final event from the run record when the Redis stream has expired, and replays
of resumed runs that don't stop at an earlier failure."""

import asyncio
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
    """Returns the given statuses in turn, then keeps the last one."""

    def __init__(self, *statuses: str, error: str | None = None) -> None:
        self.statuses = list(statuses or ["running"])
        self.error = error

    async def get(self, run_id):
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        return FakeRun(status, self.error)


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


async def test_events_stream_in_order_then_end_once_the_run_is_finished(events):
    first = await publish(events, "run.started")
    await publish(events, "step.started")
    last = await publish(events, "run.completed", pieces=1)

    frames = await collect(events, FakeRuns("completed"))

    assert len(frames) == 4
    assert frames[0].startswith(f"id: {first}\nevent: run.started\ndata: ")
    assert frames[2].startswith(f"id: {last}\nevent: run.completed\n")
    assert frames[2].endswith("\n\n")
    assert frames[3] == stream.END  # the browser closes on this, not on run events


async def test_reconnect_continues_after_the_last_seen_event(events):
    first = await publish(events, "run.started")
    await publish(events, "run.completed")

    frames = await collect(
        events, FakeRuns("completed"), after=stream.start_after(first)
    )

    assert [f.split("\n")[1] for f in frames[:-1]] == ["event: run.completed"]
    assert frames[-1] == stream.END


@pytest.mark.parametrize("header", [None, "", "garbage", "1-2-3", "$"])
def test_invalid_last_event_ids_start_from_the_beginning(header):
    assert stream.start_after(header) == "0-0"


async def test_waiting_sends_keep_alives(events, monkeypatch):
    monkeypatch.setattr(stream, "SSE_BLOCK_MS", 10)
    frames = await collect(events, FakeRuns("running"), limit=2)
    assert frames == [": keep-alive\n\n", ": keep-alive\n\n"]


async def test_expired_stream_of_a_finished_run_ends_with_its_recorded_outcome(events):
    frames = await collect(events, FakeRuns("failed", error="Something went wrong."))

    assert len(frames) == 2
    assert frames[0].startswith("event: run.failed\n")
    assert '"message":"Something went wrong."' in frames[0]
    assert frames[1] == stream.END


async def test_replay_of_a_resumed_run_continues_past_the_earlier_failure(
    events, monkeypatch
):
    """A page reload after a resume replays the old failure; the stream must go on."""
    monkeypatch.setattr(stream, "SSE_BLOCK_MS", 10)
    await publish(events, "run.started")
    await publish(events, "run.failed", message="quota")
    await publish(events, "run.started", resumed=True)

    frames = await collect(events, FakeRuns("running"), limit=4)

    assert [f.split("\n")[1] for f in frames[:3]] == [
        "event: run.started",
        "event: run.failed",
        "event: run.started",
    ]
    assert frames[3] == stream.KEEP_ALIVE


async def test_failed_run_waiting_for_its_resume_keeps_the_stream_open(
    events, monkeypatch
):
    monkeypatch.setattr(stream, "SSE_BLOCK_MS", 10)
    await publish(events, "run.started")
    await publish(events, "run.failed", message="quota")

    frames = await collect(events, FakeRuns("queued"), limit=3)

    assert frames[2] == stream.KEEP_ALIVE  # no end: the resume is coming


async def test_final_event_is_sent_once_when_the_record_lags_behind(
    events, monkeypatch
):
    """The runner publishes the final event first, then updates the record."""
    monkeypatch.setattr(stream, "SSE_BLOCK_MS", 10)
    await publish(events, "run.started")
    await publish(events, "run.completed")

    frames = await collect(events, FakeRuns("running", "completed"))

    assert [f.split("\n")[1] for f in frames[:2]] == [
        "event: run.started",
        "event: run.completed",
    ]
    assert frames[2:] == [stream.END]


async def test_after_a_final_event_the_record_is_rechecked_soon(events, monkeypatch):
    """The browser shows Retry on `end`, so it must not wait a full keep-alive."""
    monkeypatch.setattr(stream, "SSE_BLOCK_MS", 5_000)
    monkeypatch.setattr(stream, "RECHECK_MS", 10)
    await publish(events, "run.failed", message="boom")

    frames = await asyncio.wait_for(collect(events, FakeRuns("running", "failed")), 2)

    assert frames[-1] == stream.END


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
