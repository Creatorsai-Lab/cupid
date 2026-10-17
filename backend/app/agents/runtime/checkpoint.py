"""Run checkpoints: saved after every step so a run resumes where it stopped.

Serialization is strict: the checkpointer may only rebuild our own contract
types (derived from RunState, so a new state field can't be forgotten). By
default LangGraph rebuilds any class it finds in a checkpoint and only logs a
warning; that will be blocked in a future version, and it would let tampered
checkpoint data construct arbitrary objects.

Postgres checkpoints use psycopg (async), which can't run on Windows' default
event loop: the worker selects a compatible loop at startup (see worker.py).
"""

import types
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Union, get_args, get_origin, get_type_hints

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import BaseModel

from app.agents.state import RunState
from app.core.db import psycopg_url


def checkpoint_types() -> set[type[BaseModel]]:
    """Every Pydantic model the run state can contain, including nested ones."""
    found: set[type[BaseModel]] = set()

    def visit(hint: object) -> None:
        if isinstance(hint, type) and issubclass(hint, BaseModel):
            if hint in found:
                return
            found.add(hint)
            for field in hint.model_fields.values():
                visit(field.annotation)
            return
        origin = get_origin(hint)
        if origin is Annotated:
            visit(get_args(hint)[0])
        elif origin is not None or isinstance(hint, types.UnionType) or origin is Union:
            for arg in get_args(hint):
                visit(arg)

    for hint in get_type_hints(RunState).values():
        visit(hint)
    return found


def checkpoint_serde() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=checkpoint_types())


@asynccontextmanager
async def open_checkpointer(database_url: str) -> AsyncIterator[AsyncPostgresSaver]:
    """A Postgres checkpointer; creates its tables on first use (idempotent)."""
    async with AsyncPostgresSaver.from_conn_string(
        psycopg_url(database_url), serde=checkpoint_serde()
    ) as saver:
        await saver.setup()
        yield saver
