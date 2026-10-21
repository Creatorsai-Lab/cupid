"""The pipeline graph: routing, step ownership, retries, and resuming a crashed run
from its last checkpoint without re-running finished steps."""

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from app.agents.graph import PLACEHOLDER_STEPS, Steps, build_graph
from app.agents.llm.errors import RetryableProviderError
from app.agents.research_agents.models import ResearchPack
from app.agents.runtime.checkpoint import checkpoint_serde
from app.agents.runtime.retry import STEP_RETRY
from app.agents.supervisor_agents.models import RunPlan
from tests.agents.test_contracts import make_request

# The real retry rule, minus the wait between attempts.
FAST_RETRY = STEP_RETRY._replace(initial_interval=0.0, jitter=False)


class Calls:
    """Counts how often each step ran; wraps a step to fail a number of times first."""

    def __init__(self) -> None:
        self.count: dict[str, int] = {}

    def track(
        self,
        name: str,
        step,
        *,
        fail_times: int = 0,
        error: type[Exception] = RuntimeError,
    ):
        async def run(state):
            self.count[name] = self.count.get(name, 0) + 1
            if self.count[name] <= fail_times:
                raise error(f"{name} crashed")
            return await step(state)

        return run


def steps(calls: Calls, **overrides) -> Steps:
    base = {
        name: calls.track(name, getattr(PLACEHOLDER_STEPS, name))
        for name in ("supervisor", "research", "studio")
    }
    return Steps(**(base | overrides))


def start(**request_fields):
    return {"request": make_request(**request_fields)}


async def test_allowed_run_goes_through_every_step():
    calls = Calls()
    final = await build_graph(steps(calls)).ainvoke(start())

    assert calls.count == {"supervisor": 1, "research": 1, "studio": 1}
    assert final["plan"].verdict == "allow"
    assert final["research"].status == "skipped"  # placeholder research
    assert [p.deliverable for p in final["pieces"]] == list(final["plan"].deliverables)


async def test_blocked_run_stops_after_the_supervisor():
    calls = Calls()
    final = await build_graph(steps(calls)).ainvoke(start(prompt="   "))

    assert calls.count == {"supervisor": 1}
    assert final["plan"].verdict == "block"
    assert final["pieces"] == []  # merged fields are always present, empty here


async def test_research_is_skipped_when_the_plan_says_so():
    calls = Calls()

    async def no_research_plan(state):
        return {
            "plan": RunPlan(
                verdict="allow", needs_research=False, deliverables=("x_post",)
            )
        }

    final = await build_graph(steps(calls, supervisor=no_research_plan)).ainvoke(
        start()
    )

    assert "research" not in calls.count
    assert [p.deliverable for p in final["pieces"]] == ["x_post"]


async def test_a_step_writing_another_steps_field_fails_the_run():
    async def rogue_research(state):
        return {"plan": RunPlan(verdict="block", reason="hijacked")}

    graph = build_graph(steps(Calls(), research=rogue_research))
    with pytest.raises(PermissionError, match="research may not write 'plan'"):
        await graph.ainvoke(start())


async def test_transient_provider_failures_are_retried_within_the_step():
    calls = Calls()
    flaky = calls.track(
        "research",
        PLACEHOLDER_STEPS.research,
        fail_times=1,
        error=RetryableProviderError,
    )
    graph = build_graph(steps(calls, research=flaky), retry=FAST_RETRY)

    final = await graph.ainvoke(start())

    assert calls.count["research"] == 2
    assert final["pieces"]


async def test_other_errors_are_not_retried():
    calls = Calls()
    broken = calls.track("research", PLACEHOLDER_STEPS.research, fail_times=1)
    graph = build_graph(steps(calls, research=broken), retry=FAST_RETRY)

    with pytest.raises(RuntimeError, match="research crashed"):
        await graph.ainvoke(start())
    assert calls.count["research"] == 1


async def test_crashed_run_resumes_from_the_failed_step():
    """The core runtime promise: finished steps never run twice."""
    calls = Calls()
    crashing = calls.track("research", PLACEHOLDER_STEPS.research, fail_times=1)
    graph = build_graph(
        steps(calls, research=crashing),
        checkpointer=InMemorySaver(serde=checkpoint_serde()),
    )
    config: RunnableConfig = {"configurable": {"thread_id": "run-1"}}

    with pytest.raises(RuntimeError, match="research crashed"):
        await graph.ainvoke(start(), config)
    assert calls.count == {"supervisor": 1, "research": 1}

    final = await graph.ainvoke(None, config)  # None = resume from last checkpoint

    assert calls.count == {"supervisor": 1, "research": 2, "studio": 1}
    assert final["plan"].verdict == "allow"
    assert isinstance(final["research"], ResearchPack)
    assert final["pieces"]
