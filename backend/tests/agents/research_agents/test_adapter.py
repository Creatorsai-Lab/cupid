"""The adapter between Cupid and the research agent: what the agent may see of the
creator (the minimum, decision D6), how its result becomes the pipeline's
ResearchPack, when research counts as failed, and when a run is degraded."""

from datetime import UTC, datetime

import pytest

from app.agents.models import CreatorProfile, Issue
from app.agents.research_agents.adapter import (
    RESEARCH_FAILED,
    degradation_issues,
    persona_for,
    to_pack,
)
from app.agents.research_agents.models import (
    CandidatePage,
    EvaluatedPage,
    FinalCorpus,
    PersonaContext,
    ResearchResult,
    ResearchStatus,
    RunAudit,
)
from app.agents.runtime.retry import StepFailedError
from tests.agents.research_agents.fakes import FakeExtractor, FakeLLM, FakeSearch
from tests.agents.research_agents.test_pipeline import (
    evaluation,
    make_agent,
    make_candidate,
    make_document,
    make_plan,
    run,
)
from tests.agents.test_contracts import make_request

PUBLISHED = datetime(2026, 9, 1, tzinfo=UTC)


def make_result(
    status: ResearchStatus,
    pages: tuple[CandidatePage, ...] = (),
    **provider_usage: str,
) -> ResearchResult:
    plan = make_plan()
    evaluated = tuple(
        EvaluatedPage(
            candidate=page,
            content=f"Full text of {page.title}",
            extraction_quality=0.9,
            accepted=True,
        )
        for page in pages
    )
    return ResearchResult(
        status=status,
        brief=plan.brief,
        plan=plan,
        corpus=tuple(
            FinalCorpus(title=p.candidate.title, url=p.candidate.url, content=p.content)
            for p in evaluated
        ),
        evaluated_pages=evaluated,
        run_audit=RunAudit(provider_usage=provider_usage),
    )


# ── What the agent sees ────────────────────────────────────────


def test_the_agent_sees_only_what_research_needs() -> None:
    profile = CreatorProfile(
        name="Asha Rao",
        nickname="ashcooks",
        bio="Home cook sharing quick weeknight meals",
        content_niche="Home cooking",
        content_goal="Grow a loyal audience",
        content_intent="Teach simple recipes",
        target_age_group="25-34",
        target_country="India",
        target_audience="Working parents",
        usp="10-minute recipes",
    )

    persona = persona_for(make_request(tone="Casual"), profile)

    assert persona == PersonaContext(
        bio="Home cook sharing quick weeknight meals",
        niches=("Home cooking",),
        tone="Casual",
        audience="Working parents; age 25-34; in India",
        content_intent="Teach simple recipes",
    )
    sent = persona.model_dump_json()
    for private in ("Asha Rao", "ashcooks", "10-minute recipes"):
        assert private not in sent  # names and USP never leave Cupid (D6)


def test_without_a_profile_the_agent_still_gets_the_runs_tone() -> None:
    assert persona_for(make_request(tone="Formal"), None) == PersonaContext(
        tone="Formal"
    )


def test_blank_profile_fields_are_left_out() -> None:
    profile = CreatorProfile(content_niche="  ", target_audience="", bio=None)

    persona = persona_for(make_request(), profile)

    assert (persona.niches, persona.audience, persona.bio) == ((), None, None)


def test_the_goal_stands_in_when_there_is_no_intent() -> None:
    profile = CreatorProfile(content_goal="Grow a loyal audience")

    assert (
        persona_for(make_request(), profile).content_intent == "Grow a loyal audience"
    )


# ── The pack ───────────────────────────────────────────────────


def test_a_complete_result_becomes_numbered_sources_with_their_documents() -> None:
    first = make_candidate("cost-page", "cost", "cost.example").model_copy(
        update={"published_at": PUBLISHED}
    )
    second = make_candidate("policy-page", "policy", "policy.example")

    pack = to_pack(make_result(ResearchStatus.COMPLETE, (first, second)))

    assert pack.status == "complete"
    assert [(s.id, s.title, s.url, s.published_at) for s in pack.sources] == [
        ("S1", first.title, first.url, PUBLISHED),
        ("S2", second.title, second.url, None),
    ]
    assert [(d.source_id, d.content) for d in pack.documents] == [
        ("S1", f"Full text of {first.title}"),
        ("S2", f"Full text of {second.title}"),
    ]


@pytest.mark.parametrize(
    "status", [ResearchStatus.LOW_COVERAGE, ResearchStatus.TIMEOUT]
)
def test_a_partial_result_with_sources_continues_with_its_status(status) -> None:
    page = make_candidate("cost-page", "cost", "cost.example")

    pack = to_pack(make_result(status, (page,)))

    assert pack.status == status.value  # the runner labels the run degraded
    assert [s.id for s in pack.sources] == ["S1"]


@pytest.mark.parametrize(
    "status",
    [ResearchStatus.FAILED, ResearchStatus.TIMEOUT, ResearchStatus.LOW_COVERAGE],
)
def test_research_with_no_sources_fails_with_the_users_message(status) -> None:
    # Retried twice by the step's retry rule, then the user sees this message.
    with pytest.raises(StepFailedError) as raised:
        to_pack(make_result(status))

    assert (
        raised.value.user_message
        == RESEARCH_FAILED
        == ("Research failed. Please try again.")
    )


# ── Degraded runs ──────────────────────────────────────────────


@pytest.mark.parametrize("stage", ["planning", "evaluation"])
def test_the_offline_fallback_marks_the_run_degraded(stage) -> None:
    page = make_candidate("cost-page", "cost", "cost.example")
    result = make_result(
        ResearchStatus.COMPLETE, (page,), **{stage: "deterministic_fallback"}
    )

    [issue] = degradation_issues(result)

    assert isinstance(issue, Issue)
    assert (issue.step, issue.severity) == ("research", "degraded")
    assert "simpler" in issue.message  # said plainly, so the user knows


def test_normal_research_and_gap_fallbacks_are_not_degraded() -> None:
    page = make_candidate("cost-page", "cost", "cost.example")
    result = make_result(
        ResearchStatus.COMPLETE,
        (page,),
        planning="groq",
        evaluation="groq",
        gap_planning="deterministic_fallback",  # a routine local gap query
    )

    assert degradation_issues(result) == []


def test_a_real_agent_result_becomes_a_pack() -> None:
    # Break caught: an adapter that only works on hand-built results (for example
    # corpus URLs that don't match the evaluated pages it reads dates from).
    published = PUBLISHED
    pages = [
        make_candidate(f"{angle}-page", angle, f"{angle}.example").model_copy(
            update={"published_at": published}
        )
        for angle in ("cost", "policy", "adoption")
    ]
    agent = make_agent(
        FakeLLM(
            make_plan(),
            {"evaluations": [evaluation(p.id, p.discovered_by[0]) for p in pages]},
        ),
        FakeSearch({p.discovered_by[0]: [p] for p in pages}),
        FakeExtractor({p.url: make_document(p) for p in pages}),
    )
    result = run(agent.run("Research community solar", PersonaContext()))

    pack = to_pack(result)

    assert pack.status == "complete"
    assert {s.url for s in pack.sources} == {p.url for p in pages}
    assert all(s.published_at is not None for s in pack.sources)
    assert {d.content for d in pack.documents} == {c.content for c in result.corpus}
    assert degradation_issues(result) == []
