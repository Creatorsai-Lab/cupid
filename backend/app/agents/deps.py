"""Dependencies for the agents endpoints; tests override them with fakes."""

from functools import lru_cache

from saq.queue.postgres import PostgresQueue

from app.agents.runtime.events import EventStream
from app.agents.runtime.queue import make_queue
from app.agents.runtime.runs import RunStore
from app.core.db import async_session
from app.core.redis import redis_client


def get_run_store() -> RunStore:
    return RunStore(async_session)


def get_event_stream() -> EventStream:
    return EventStream(redis_client)


@lru_cache(maxsize=1)
def get_run_queue() -> PostgresQueue:
    """One queue client per API process; the app's lifespan connects it."""
    return make_queue()
