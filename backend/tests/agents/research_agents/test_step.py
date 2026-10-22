"""The research step: one fresh agent per run on the worker's shared providers,
its result adapted into the run state, failures and degradation passed on."""

from dataclasses import replace

import pytest

from app.agents.graph import PLACEHOLDER_STEPS, Steps, build_graph
from app.agents.research_agents.config import CONFIG
from app.agents.research_agents.step import ResearchStep
from app.agents.runtime.retry import StepFailedError
from tests.agents.research_agents.fakes import FakeExtractor, FakeLLM, FakeSearch
from tests.agents.research_agents.test_pipeline import (
    evaluation,
    make_candidate,
    make_document,
    make_plan,
)
from tests.agents.test_contracts import make_request

# The fake planner researches community solar, and the fake pages are short: the
# request must match the plan (the agent rejects a plan that doesn't), and the test
# config accepts short articles, as the pipeline tests do.
PROMPT = "Research community solar"
TEST_CONFIG = replace(CONFIG, minimum_article_chars=100)


class FakeGateway:
    """Hands out one session per run, like the real gateway."""

    def __init__(self, llm: FakeLLM) -> None:
        self.llm = llm
        self.run_ids: list[str] = []

    def session(self, run_id: str) -> FakeLLM:
        self.run_ids.append(run_id)
        return self.llm


def complete_research(*evaluation_answers):
    pages = [
        make_candidate(f"{angle}-page", angle, f"{angle}.example")
        for angle in ("cost", "policy", "adoption")
    ]
    llm = FakeLLM(
        make_plan(),
        *(
            evaluation_answers
            or ({"evaluations": [evaluation(p.id, p.discovered_by[0]) for p in pages]},)
        ),
    )
    search = FakeSearch({p.discovered_by[0]: [p] for p in pages})
    extractor = FakeExtractor({p.url: make_document(p) for p in pages})
    return llm, search, extractor


async def test_a_run_gets_its_own_session_and_a_research_pack():
    llm, search, extractor = complete_research()
    gateway = FakeGateway(llm)
    step = ResearchStep(gateway, search, extractor, TEST_CONFIG)

    update = await step({"request": make_request(run_id="run-7", prompt=PROMPT)})

    assert gateway.run_ids == ["run-7"]
    assert update["research"].status == "complete"
    assert len(update["research"].sources) == 3
    assert "issues" not in update
    assert not (search.closed or extractor.closed)  # the worker owns them


async def test_research_without_sources_fails_the_attempt():
    step = ResearchStep(
        FakeGateway(FakeLLM(make_plan())), FakeSearch(), FakeExtractor(), TEST_CONFIG
    )

    with pytest.raises(StepFailedError):
        await step({"request": make_request(prompt=PROMPT)})


async def test_offline_scoring_passes_on_a_degraded_issue():
    # Every provider failed (not on quota) while scoring pages: the agent ranks them
    # offline, and the run must say so instead of looking complete.
    llm, search, extractor = complete_research(RuntimeError("every provider failed"))
    step = ResearchStep(FakeGateway(llm), search, extractor, TEST_CONFIG)

    update = await step({"request": make_request(prompt=PROMPT)})

    assert update["research"].sources
    assert [(i.step, i.severity) for i in update["issues"]] == [
        ("research", "degraded")
    ]


async def test_the_step_runs_inside_the_pipeline_graph():
    # Break caught: the step writing a field it doesn't own (the graph refuses it).
    llm, search, extractor = complete_research()
    steps = Steps(
        supervisor=PLACEHOLDER_STEPS.supervisor,
        research=ResearchStep(FakeGateway(llm), search, extractor, TEST_CONFIG),
        studio=PLACEHOLDER_STEPS.studio,
    )

    final = await build_graph(steps).ainvoke({"request": make_request(prompt=PROMPT)})

    assert final["research"].status == "complete"
    assert final["pieces"]
