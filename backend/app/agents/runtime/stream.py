"""Turns a run's Redis event stream into Server-Sent Events for the browser.

- Each frame carries its stream id, so the browser's automatic reconnect
  (Last-Event-ID) continues exactly where it stopped.
- The stream ends after the run's final event.
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
    while not await is_disconnected():
        batch = await events.read(run_id, after, block_ms=block_ms)
        block_ms = SSE_BLOCK_MS
        for entry_id, event in batch:
            after = entry_id
            yield sse(event, entry_id)
            if event.type in TERMINAL_EVENTS:
                return
        if batch:
            continue
        run = await runs.get(run_id)
        if run is not None and run.status in _FINAL_EVENT:
            data = {"message": run.error} if run.error else {}
            yield sse(RunEvent(run_id=run_id, type=_FINAL_EVENT[run.status], data=data))
            return
        yield KEEP_ALIVE
