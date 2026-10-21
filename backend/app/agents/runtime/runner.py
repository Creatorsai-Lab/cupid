"""Runs the pipeline for one run: start and resume are the same call.

    await execute(rt, run_id, request)   # start a new run
    await execute(rt, run_id)            # resume from the last checkpoint

Progress goes to the run's event stream as it happens; the outcome goes to the
run record. Failures show the user a safe message; details go to the logs only.

The queue can deliver a job twice (SAQ's sweep can retry a job it sees mid-
dequeue), so a run executes only while holding its lock, and only if it is
queued, or still "running" because its worker died. Any other job is a
duplicate and does nothing.
"""

import asyncio
import logging
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from app.agents.models import (
    CreatorProfile,
    EventType,
    RunEvent,
    RunRequest,
    RunStatus,
)
from app.agents.runtime.events import EventStream
from app.agents.runtime.retry import StepFailedError, resume_later
from app.agents.state import RunState

logger = logging.getLogger("app.agents.runtime")

USER_ERROR = "Something went wrong while creating your content. You can retry this run."
NOTHING_TO_RESUME = "This run can't be resumed: it was never started."
DEGRADED_RESEARCH = {"low_coverage", "timeout", "failed"}
RUN_TIMEOUT_S = (
    15 * 60
)  # then the run fails, resumable; a hung step can't hold a worker
RUNNABLE: set[str] = {"queued", "running"}  # running: its worker died mid-run


class RunStatusStore(Protocol):
    def exclusive(self, run_id: str) -> AbstractAsyncContextManager[bool]: ...

    async def get(self, run_id: str) -> Any: ...  # the run record, or None

    async def set_status(
        self, run_id: str, status: RunStatus, *, error: str | None = None
    ) -> None: ...


@dataclass(frozen=True)
class RunOutcome:
    status: RunStatus | Literal["skipped"]  # skipped: a duplicate job, nothing done
    resume_later: bool = False  # failed on provider quota: resume once it recovers


@dataclass(frozen=True)
class Runtime:
    """What a run needs: the compiled graph (with its checkpointer), events, records."""

    graph: CompiledStateGraph
    events: EventStream
    runs: RunStatusStore
    timeout_s: float = RUN_TIMEOUT_S


async def execute(
    rt: Runtime,
    run_id: str,
    request: RunRequest | None = None,
    profile: CreatorProfile | None = None,
) -> RunOutcome:
    """`request` and `profile` (the creator's profile when the run was created)
    start a run; without them it resumes. Both are inputs saved in the first
    checkpoint, so a resume never needs them again."""
    async with rt.runs.exclusive(run_id) as mine:
        run = await rt.runs.get(run_id) if mine else None
        if run is None or run.status not in RUNNABLE:
            logger.warning("run %s: duplicate job skipped", run_id)
            return RunOutcome("skipped")
        return await _execute(rt, run_id, request, profile)


async def _execute(
    rt: Runtime,
    run_id: str,
    request: RunRequest | None,
    profile: CreatorProfile | None,
) -> RunOutcome:
    config: RunnableConfig = {"configurable": {"thread_id": run_id}}

    async def publish(type_: EventType, step: str | None = None, **data: Any) -> None:
        await rt.events.publish(
            RunEvent(run_id=run_id, type=type_, step=step, data=data)
        )

    if (await rt.graph.aget_state(config)).values:
        # Resume. A start job delivered twice (e.g. after a worker crash) must not
        # restart the run from scratch on top of its own checkpoints.
        request = None
    elif request is None:
        await publish("run.failed", message=NOTHING_TO_RESUME, resume_later=False)
        await rt.runs.set_status(run_id, "failed", error=NOTHING_TO_RESUME)
        return RunOutcome("failed")

    await rt.runs.set_status(run_id, "running")
    await publish("run.started", resumed=request is None)
    payload: dict[str, Any] | None = None  # None: continue from the last checkpoint
    if request is not None:
        payload = {"request": request} | ({"profile": profile} if profile else {})

    try:
        async with asyncio.timeout(rt.timeout_s):  # TimeoutError: failed, resumable
            async for mode, chunk in rt.graph.astream(
                payload, config, stream_mode=["tasks", "updates"], durability="sync"
            ):
                if not isinstance(chunk, dict):  # both stream modes yield dicts
                    continue
                if mode == "tasks":
                    if "input" in chunk:
                        await publish("step.started", chunk["name"])
                    elif chunk.get("error") is None:
                        await publish("step.finished", chunk["name"])
                else:
                    for step, update in chunk.items():
                        await _publish_outputs(publish, step, update or {})
    except Exception as error:  # every failure ends here; the run stays resumable
        message = (
            error.user_message if isinstance(error, StepFailedError) else USER_ERROR
        )
        logger.exception("run %s failed", run_id)
        later = resume_later(error)
        await publish("run.failed", message=message, resume_later=later)
        await rt.runs.set_status(run_id, "failed", error=message)
        return RunOutcome("failed", resume_later=later)

    state = cast(RunState, (await rt.graph.aget_state(config)).values)
    status, event_type, data = _outcome(state)
    # Final event before the final status: a live stream that sees the run finished
    # in the database can then rely on the final event already being in Redis.
    await publish(event_type, **data)
    await rt.runs.set_status(run_id, status)
    return RunOutcome(status)


async def _publish_outputs(publish, step: str, update: dict[str, Any]) -> None:
    """Results the UI can show before the run ends: sources, then each draft."""
    if (pack := update.get("research")) is not None:
        await publish(
            "research.sources",
            step,
            status=pack.status,
            sources=[s.model_dump(mode="json") for s in pack.sources],
        )
    for piece in update.get("pieces") or []:
        await publish("piece.ready", step, **piece.model_dump(mode="json"))


def _outcome(state: RunState) -> tuple[RunStatus, EventType, dict[str, Any]]:
    plan = state.get("plan")
    if plan is not None and plan.verdict == "block":
        return "blocked", "run.blocked", {"reason": plan.reason}
    issues = [i for i in state.get("issues", []) if i.severity in ("degraded", "error")]
    research = state.get("research")
    if issues or (research is not None and research.status in DEGRADED_RESEARCH):
        return (
            "degraded",
            "run.degraded",
            {
                "issues": [i.model_dump() for i in issues],
                "research": research.status if research is not None else None,
            },
        )
    return "completed", "run.completed", {"pieces": len(state.get("pieces", []))}
