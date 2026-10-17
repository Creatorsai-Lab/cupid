"""Runs the pipeline for one run: start and resume are the same call.

    await execute(rt, run_id, request)   # start a new run
    await execute(rt, run_id)            # resume from the last checkpoint

Progress goes to the run's event stream as it happens; the outcome goes to the
run record. Failures show the user a safe message; details go to the logs only.
"""

import logging
from dataclasses import dataclass
from typing import Any, Protocol, cast

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from app.agents.models import EventType, RunEvent, RunRequest, RunStatus
from app.agents.runtime.events import EventStream
from app.agents.runtime.retry import resume_later
from app.agents.state import RunState

logger = logging.getLogger("app.agents.runtime")

USER_ERROR = "Something went wrong while creating your content. You can retry this run."
NOTHING_TO_RESUME = "This run can't be resumed: it was never started."
DEGRADED_RESEARCH = {"low_coverage", "timeout", "failed"}


class RunStatusStore(Protocol):
    async def set_status(
        self, run_id: str, status: RunStatus, *, error: str | None = None
    ) -> None: ...


@dataclass(frozen=True)
class Runtime:
    """What a run needs: the compiled graph (with its checkpointer), events, records."""

    graph: CompiledStateGraph
    events: EventStream
    runs: RunStatusStore


async def execute(
    rt: Runtime, run_id: str, request: RunRequest | None = None
) -> RunStatus:
    config: RunnableConfig = {"configurable": {"thread_id": run_id}}

    async def publish(type_: EventType, step: str | None = None, **data: Any) -> None:
        await rt.events.publish(
            RunEvent(run_id=run_id, type=type_, step=step, data=data)
        )

    if request is None and not (await rt.graph.aget_state(config)).values:
        await rt.runs.set_status(run_id, "failed", error=NOTHING_TO_RESUME)
        await publish("run.failed", message=NOTHING_TO_RESUME, resume_later=False)
        return "failed"

    await rt.runs.set_status(run_id, "running")
    await publish("run.started", resumed=request is None)
    payload = {"request": request} if request is not None else None

    try:
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
        logger.exception("run %s failed", run_id)
        await rt.runs.set_status(run_id, "failed", error=USER_ERROR)
        await publish(
            "run.failed", message=USER_ERROR, resume_later=resume_later(error)
        )
        return "failed"

    state = cast(RunState, (await rt.graph.aget_state(config)).values)
    status, event_type, data = _outcome(state)
    await rt.runs.set_status(run_id, status)
    await publish(event_type, **data)
    return status


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
