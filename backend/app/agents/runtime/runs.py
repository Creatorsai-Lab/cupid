"""Reading and writing run records. Each call uses its own short session; only
the execution lock keeps one connection for the length of a run."""

import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from sqlalchemy import func, select, update
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

    async def claim_for_resume(self, run_id: str, user_id: uuid.UUID | None) -> bool:
        """Atomically move a failed run back to queued; True for exactly one caller.

        One UPDATE ... WHERE status = 'failed': if two resume requests race, the
        database lets only one of them match, so a run is never queued twice.
        user_id=None is for the worker's own automatic resume.
        """
        try:
            key = uuid.UUID(run_id)
        except ValueError:
            return False
        conditions = [AgentRun.id == key, AgentRun.status == "failed"]
        if user_id is not None:
            conditions.append(AgentRun.user_id == user_id)
        async with self._sessions() as session:
            result = await session.execute(
                update(AgentRun)
                .where(*conditions)
                .values(status="queued", error=None)
                .returning(AgentRun.id)
            )
            claimed = result.scalar_one_or_none() is not None
            await session.commit()
        return claimed

    @asynccontextmanager
    async def exclusive(self, run_id: str) -> AsyncIterator[bool]:
        """Hold the run's execution lock inside the block; False if another
        execution holds it (the queue can deliver a job twice).

        A Postgres advisory lock tied to this transaction: released when the block
        ends, or by the database itself if the worker dies, so it never leaks.
        """
        key = int.from_bytes(uuid.UUID(run_id).bytes[:8], "big", signed=True)
        async with self._sessions() as session:
            yield bool(
                await session.scalar(select(func.pg_try_advisory_xact_lock(key)))
            )
