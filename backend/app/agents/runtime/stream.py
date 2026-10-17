"""Turns a run's Redis event stream into Server-Sent Events for the browser.

- Each frame carries its stream id, so the browser's automatic reconnect
  (Last-Event-ID) continues exactly where it stopped.
- The stream ends with an explicit `end` event, sent once the run record says
  the run is finished. A final event alone doesn't end it: a resumed run's
  stream holds an earlier run.failed, and a page reload replays it.
  (EventSource reconnects whenever a response ends, so the browser closes on
  `end`.)
- While waiting it sends keep-alive comments, so proxies don't close it.
- If the Redis stream has expired (runs older than 24 h), the final event is
  rebuilt from the run record instead of waiting forever.
"""

import re
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

from app.agents.models import TERMINAL_EVENTS, EventType, RunEvent
from app.agents.runtime.events import EventStream

SSE_BLOCK_MS = 15_000  # wait per read; also the keep-alive interval
KEEP_ALIVE = ": keep-alive\n\n"
END = "event: end\ndata: {}\n\n"
# After a final event the record is usually updated within milliseconds (the
# runner publishes first), so look again soon rather than after a keep-alive.
RECHECK_MS = 1_000
_STREAM_ID = re.compile(r"\d+-\d+")
_FINAL_EVENT: dict[str, EventType] = {
    "completed": "run.completed",
    "degraded": "run.degraded",
    "failed": "run.failed",
    "blocked": "run.blocked",
}


class RunReader(Protocol):
    async def get(self, run_id: str) -> Any: ...


def start_after(last_event_id: str | None) -> str:
    """Where to resume: the browser's Last-Event-ID if valid, else the beginning."""
    if last_event_id and _STREAM_ID.fullmatch(last_event_id):
        return last_event_id
    return "0-0"


def sse(event: RunEvent, entry_id: str | None = None) -> str:
    head = f"id: {entry_id}\n" if entry_id else ""
    return f"{head}event: {event.type}\ndata: {event.model_dump_json()}\n\n"


async def event_stream(
    run_id: str,
    *,
    events: EventStream,
    runs: RunReader,
    after: str,
    is_disconnected: Callable[[], Awaitable[bool]],
) -> AsyncIterator[str]:
    block_ms: int | None = None  # first read returns at once; then wait for news
    ended_with_final = False  # the last event sent was a run's final event
    while not await is_disconnected():
        batch = await events.read(run_id, after, block_ms=block_ms)
        block_ms = SSE_BLOCK_MS
        for entry_id, event in batch:
            after = entry_id
            ended_with_final = event.type in TERMINAL_EVENTS
            yield sse(event, entry_id)
        if batch and not ended_with_final:
            continue
        run = await runs.get(run_id)
        if run is not None and run.status in _FINAL_EVENT:
            if not ended_with_final:  # e.g. the Redis stream expired
                data = {"message": run.error} if run.error else {}
                yield sse(
                    RunEvent(run_id=run_id, type=_FINAL_EVENT[run.status], data=data)
                )
            yield END
            return
        if batch:  # ended with a final event, but the record isn't final yet
            block_ms = RECHECK_MS
        else:
            yield KEEP_ALIVE
