"""Run progress events on a Redis stream, one stream per run.

The worker publishes; the SSE endpoint reads. Every event gets a stream id, so
a browser that reconnects with Last-Event-ID continues exactly where it left
off. Streams are capped in length and expire a day after their last event.
"""

from redis.asyncio import Redis

from app.agents.models import RunEvent

STREAM_TTL_S = 24 * 60 * 60
STREAM_MAXLEN = 1_000  # far above any real run; guards against a runaway loop


def stream_key(run_id: str) -> str:
    return f"run:{run_id}:events"


class EventStream:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def publish(self, event: RunEvent) -> str:
        """Append an event; returns its stream id."""
        key = stream_key(event.run_id)
        entry_id = await self.redis.xadd(
            key, {"event": event.model_dump_json()}, maxlen=STREAM_MAXLEN
        )
        await self.redis.expire(key, STREAM_TTL_S)
        return str(entry_id)

    async def read(
        self, run_id: str, after: str = "0-0", *, block_ms: int | None = None
    ) -> list[tuple[str, RunEvent]]:
        """Events after `after` (oldest first); waits up to block_ms for new ones."""
        response = await self.redis.xread(
            {stream_key(run_id): after}, count=100, block=block_ms
        )
        return [
            (str(entry_id), RunEvent.model_validate_json(fields["event"]))
            for _, entries in response or []
            for entry_id, fields in entries
        ]
