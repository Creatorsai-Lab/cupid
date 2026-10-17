"""Starting a run: what POST /generate does, outside the HTTP layer."""

import logging
import uuid

from saq import Queue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import CreatorProfile, RunRequest
from app.agents.runtime.queue import enqueue_run
from app.agents.runtime.runner import USER_ERROR
from app.agents.runtime.runs import RunStore
from app.agents.schemas import GenerateRequest
from app.auth.models import User
from app.core.errors import ServiceUnavailableError
from app.profile.models import UserPersonalization

logger = logging.getLogger("app.agents")

_PROFILE_FIELDS = tuple(name for name in CreatorProfile.model_fields if name != "name")


async def creator_profile(db: AsyncSession, user: User) -> CreatorProfile:
    """The creator's profile as it is now; the run keeps this snapshot."""
    row = await db.scalar(
        select(UserPersonalization).where(UserPersonalization.user_id == user.id)
    )
    if row is None:
        return CreatorProfile(name=user.full_name or None)
    return CreatorProfile(
        name=row.name or user.full_name or None,
        **{field: getattr(row, field) for field in _PROFILE_FIELDS},
    )


async def start_run(
    body: GenerateRequest,
    user: User,
    profile: CreatorProfile,
    *,
    runs: RunStore,
    queue: Queue,
) -> str:
    """Record the run as queued and queue its start job; returns the run id.

    If the job can't be queued, the run is marked failed (never left "queued"
    with nothing to run it) and the user is asked to try again.
    """
    request = RunRequest(
        run_id=str(uuid.uuid4()), user_id=str(user.id), **body.model_dump()
    )
    await runs.create(request)
    try:
        queued = await enqueue_run(queue, request.run_id, request, profile=profile)
    except Exception:
        logger.exception("run %s: start job could not be queued", request.run_id)
        queued = False
    if not queued:
        await runs.set_status(request.run_id, "failed", error=USER_ERROR)
        raise ServiceUnavailableError("The run could not be queued. Please try again.")
    return request.run_id
