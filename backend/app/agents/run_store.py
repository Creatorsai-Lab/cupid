"""
Redis-backed store for agent run state.

Replaces the in-memory AGENT_RUNS dict. Two reasons:
1. Memory leak — the old dict never evicted; each run held full page text
forever.
2. Multi-worker — generate and poll can land on different workers. An
in-process
    dict is invisible to the other worker → 404. Redis is shared.

Model: the background pipeline owns the run dict locally and writes a whole
snapshot on each update (single writer, so no read-modify-write race). The
poll
endpoint only reads. Runs expire after RUN_TTL_SECONDS.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.redis import redis_client

KEY_PREFIX = "agent_run:"
RUN_TTL_SECONDS = 60 * 60


def _key(run_id: str) -> str:
    return f"{KEY_PREFIX}{run_id}"


async def save_run(run_id: str, data: dict[str, Any]) -> None:
    """Write a full snapshot of the run. Resets the TTL each call."""
    # default=str serializes datetime (created_at) to ISO; pydantic parses it back.
    payload = json.dumps(data, default=str)
    await redis_client.set(_key(run_id), payload, ex=RUN_TTL_SECONDS)


async def load_run(run_id: str) -> dict[str, Any] | None:
    """Read a run snapshot, or None if missing/expired."""
    raw = await redis_client.get(_key(run_id))
    if raw is None:
        return None
    return json.loads(raw)
