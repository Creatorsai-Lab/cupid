"""Agents API: start a run, follow it live, resume it.

- POST /api/v1/agents/generate          queue a new run (returns its id)
- GET  /api/v1/agents/runs/{id}         the run's record (status, error)
- GET  /api/v1/agents/runs/{id}/events  live progress (Server-Sent Events)
- POST /api/v1/agents/runs/{id}/resume  continue a failed run

Runs execute in the worker (app/agents/runtime/worker.py), never in the API.
"""

import uuid

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from saq.queue.postgres import PostgresQueue

from app.agents.deps import get_event_stream, get_run_queue, get_run_store
from app.agents.runtime.events import EventStream
from app.agents.runtime.queue import enqueue_run
from app.agents.runtime.runner import USER_ERROR
from app.agents.runtime.runs import RunStore
from app.agents.runtime.stream import event_stream, start_after
from app.agents.schemas import GenerateRequest, GenerateResponse, RunSnapshot
from app.agents.service import creator_profile, start_run
from app.auth.deps import CurrentUser
from app.core.db import DbSession
from app.core.errors import ConflictError, NotFoundError, ServiceUnavailableError

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.post("/generate", response_model=GenerateResponse)
async def generate_content(
    body: GenerateRequest,
    user: CurrentUser,
    db: DbSession,
    runs: RunStore = Depends(get_run_store),
    queue: PostgresQueue = Depends(get_run_queue),
) -> GenerateResponse:
    """Queue a run; follow it at /runs/{run_id}/events."""
    profile = await creator_profile(db, user)
    run_id = await start_run(body, user, profile, runs=runs, queue=queue)
    return GenerateResponse(
        run_id=run_id,
        status="queued",
        message="Run queued. Follow it at /api/v1/agents/runs/{run_id}/events.",
    )


@router.get("/runs/{run_id}", response_model=RunSnapshot)
async def get_run(
    run_id: str, user: CurrentUser, runs: RunStore = Depends(get_run_store)
) -> RunSnapshot:
    run = await runs.get_for_user(run_id, user.id)
    if run is None:
        raise NotFoundError("Run not found")
    return RunSnapshot(
        run_id=str(run.id),
        status=run.status,  # type: ignore[arg-type]  # the database checks it
        error=run.error,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: str,
    request: Request,
    user: CurrentUser,
    runs: RunStore = Depends(get_run_store),
    events: EventStream = Depends(get_event_stream),
    last_event_id: str | None = Header(default=None),
) -> StreamingResponse:
    """Live run progress as Server-Sent Events; reconnects continue via Last-Event-ID."""
    if await runs.get_for_user(run_id, user.id) is None:
        raise NotFoundError("Run not found")
    return StreamingResponse(
        event_stream(
            run_id,
            events=events,
            runs=runs,
            after=start_after(last_event_id),
            is_disconnected=request.is_disconnected,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/runs/{run_id}/resume", status_code=202)
async def resume_run(
    run_id: str,
    user: CurrentUser,
    runs: RunStore = Depends(get_run_store),
    queue: PostgresQueue = Depends(get_run_queue),
) -> dict[str, str]:
    """Continue a failed run from its last checkpoint."""
    if await runs.get_for_user(run_id, user.id) is None:
        raise NotFoundError("Run not found")
    if not await runs.claim_for_resume(run_id, user.id):
        raise ConflictError("Only a failed run can be resumed.")
    if not await enqueue_run(queue, run_id, attempt=f"manual-{uuid.uuid4().hex[:12]}"):
        await runs.set_status(run_id, "failed", error=USER_ERROR)
        raise ServiceUnavailableError("The run could not be queued. Please try again.")
    return {"run_id": run_id, "status": "queued"}
