"""Wiring only: which step runs after which. No business logic lives here.

    supervisor ──► research ──► studio ──► END
        │ blocked ──────────────────────► END
        └ no research needed ─► studio

Steps are passed in (`Steps`), so tests use placeholders or fakes and the
runtime binds real agents to their dependencies (LLM session, clients).
Every step's output goes through check_update(): a step that writes a field
it doesn't own fails the run immediately.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from app.agents.research_agents.agent import research
from app.agents.runtime.retry import STEP_RETRY
from app.agents.state import RunState, check_update
from app.agents.studio_agents.agent import create
from app.agents.supervisor_agents.agent import supervise


class Step(Protocol):
    """A pipeline step: reads the run state, returns the fields it updates."""

    async def __call__(self, state: RunState) -> dict[str, Any]: ...


@dataclass(frozen=True)
class Steps:
    supervisor: Step
    research: Step
    studio: Step


PLACEHOLDER_STEPS = Steps(supervisor=supervise, research=research, studio=create)


def build_graph(
    steps: Steps = PLACEHOLDER_STEPS,
    *,
    checkpointer: BaseCheckpointSaver | None = None,
    retry: RetryPolicy = STEP_RETRY,
) -> CompiledStateGraph:
    graph = StateGraph(RunState)
    for name in ("supervisor", "research", "studio"):
        graph.add_node(name, _guarded(name, getattr(steps, name)), retry_policy=retry)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor", _after_supervisor, ["research", "studio", END]
    )
    graph.add_edge("research", "studio")
    graph.add_edge("studio", END)
    return graph.compile(checkpointer=checkpointer)


def _guarded(name: str, step: Step) -> Step:
    async def run(state: RunState) -> dict[str, Any]:
        return check_update(name, await step(state))

    return run


def _after_supervisor(state: RunState) -> str:
    plan = state.get("plan")
    if plan is None:
        raise RuntimeError("supervisor finished without writing a plan")
    if plan.verdict == "block":
        return END
    return "research" if plan.needs_research else "studio"
