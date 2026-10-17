"""Reading and writing run records. Each call uses its own short session, so the
worker never holds a database connection open for the length of a run."""

import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import RunRequest, RunStatus
from app.agents.runtime.models import AgentRun

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class RunStore:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    async def create(self, request: RunRequest) -> AgentRun:
        run = AgentRun(
            id=uuid.UUID(request.run_id),
            user_id=uuid.UUID(request.user_id),
            status="queued",
            request=request.model_dump(mode="json"),
        )
        async with self._sessions() as session:
            session.add(run)
            await session.commit()
        return run

    async def set_status(
        self, run_id: str, status: RunStatus, *, error: str | None = None
    ) -> None:
        async with self._sessions() as session:
            await session.execute(
                update(AgentRun)
                .where(AgentRun.id == uuid.UUID(run_id))
                .values(status=status, error=error)
            )
            await session.commit()

    async def get(self, run_id: str) -> AgentRun | None:
        async with self._sessions() as session:
            return await session.get(AgentRun, uuid.UUID(run_id))

    async def get_for_user(self, run_id: str, user_id: uuid.UUID) -> AgentRun | None:
        """The run if this user owns it; None otherwise (never reveals other users' runs)."""
        try:
            key = uuid.UUID(run_id)
        except ValueError:
            return None
        async with self._sessions() as session:
            return await session.scalar(
                select(AgentRun).where(AgentRun.id == key, AgentRun.user_id == user_id)
            )
