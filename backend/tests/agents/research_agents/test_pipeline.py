# Ported tests read optional result fields that the test has already checked;
# pyright can't see those checks. To tighten later (plan: Later).
# pyright: reportOptionalMemberAccess=false
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.agents.llm.errors import NoProviderAvailableError, RateLimitedError
from app.agents.research_agents.agent import ResearchAgent
from app.agents.research_agents.config import CONFIG
from app.agents.research_agents.filters import clean_article_content
from app.agents.research_agents.interfaces import (
    SearchProvider,
)
from app.agents.research_agents.models import (
    BackupQuery,
    CandidatePage,
    ExtractedDocument,
    FreshnessMode,
    PersonaContext,
    PlannedQuery,
    ResearchBrief,
    ResearchErrorType,
    ResearchPlan,
    ResearchStatus,
)
from app.agents.research_agents.providers import ExtractionError
from tests.agents.research_agents.fakes import FakeExtractor, FakeLLM, FakeSearch

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)


def run(coro):
    return asyncio.run(coro)


def make_plan() -> ResearchPlan:
    return ResearchPlan.model_validate(
        {
            "brief": {
                "topic": "community solar",
                "user_goal": "Explain the evidence and practical tradeoffs",
                "required_angles": ["cost", "policy", "adoption"],
                "language": "en",
                "freshness_mode": FreshnessMode.EVERGREEN,
                "search_query_count": 3,
            },
            "queries": [
                {
                    "id": "cost",
                    "query": "community solar cost analysis",
                    "purpose": "cost",
                    "intent": "data",
                },
                {
                    "id": "policy",
                    "query": "community solar policy regulation",
                    "purpose": "policy",
                    "intent": "news",
                },
                {
                    "id": "adoption",
                    "query": "community solar adoption data",
                    "purpose": "adoption",
                    "intent": "data",
                },
            ],
        }
    )


def with_backup(
    plan: ResearchPlan, query: str, angle: str = "adoption"
) -> ResearchPlan:
    return plan.model_copy(
        update={"backup_queries": (BackupQuery(angle=angle, query=query),)}
    )


def make_candidate(identifier: str, query_id: str, domain: str) -> CandidatePage:
    url = f"https://{domain}/reports/{identifier}"
    return CandidatePage(
        id=identifier,
        url=url,
        canonical_url=url,
        publisher_domain=domain,
        search_provider="tavily",
        title=f"Community solar evidence {identifier}",
        snippet="Evidence about community solar.",
        discovered_by=(query_id,),
        search_rank=1,
    )


def make_document(page: CandidatePage) -> ExtractedDocument:
    return ExtractedDocument(
        candidate_id=page.id,
        content=(
            f"Title: {page.title}\nMarkdown Content:\n\n# {page.title}\n\n"
            + (
                f"Complete substantive evidence for {page.id}; café and an em dash — are preserved. "
                * 20
            )
        ),
        title=page.title,
        extraction_provider="fake-reader",
        article_type="Article",
    )


def evaluation(identifier: str, angle: str) -> dict[str, object]:
    return {
        "candidate_id": identifier,
        "relevance": 9,
        "freshness": 8,
        "authority": 8,
        "content_quality": 9,
        "persona_utility": 5,
        "covered_angles": [angle],
        "justification": f"Direct evidence for {angle}.",
    }


def make_agent(
    llm: FakeLLM,
    search: SearchProvider,
    extractor: FakeExtractor,
    **config_values: object,
) -> ResearchAgent:
    config = replace(CONFIG, minimum_article_chars=100, **config_values)
    return ResearchAgent(
        config=config, llm=llm, search=search, extractor=extractor, now=lambda: NOW
    )


def test_run_delivers_complete_cleaned_corpus_with_only_composer_fields() -> None:
    # Break caught: orchestration leaking source metadata or passing a ranking view/snippet instead of full cleaned content.
    plan = make_plan()
    pages = [
        make_candidate("cost-page", "cost", "cost.example"),
        make_candidate("policy-page", "policy", "policy.example"),
        make_candidate("adoption-page", "adoption", "adoption.example"),
    ]
    documents = {page.url: make_document(page) for page in pages}
    agent = make_agent(
        FakeLLM(
            plan,
            {
                "evaluations": [
                    evaluation("cost-page", "cost"),
                    evaluation("policy-page", "policy"),
                    evaluation("adoption-page", "adoption"),
                ]
            },
        ),
        FakeSearch({"cost": [pages[0]], "policy": [pages[1]], "adoption": [pages[2]]}),
        FakeExtractor(documents),
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.COMPLETE
    assert len(result.corpus) == 3
    assert {item.title: item.content for item in result.composer_corpus()} == {
        page.title: clean_article_content(documents[page.url].content) for page in pages
    }
    assert all(
        set(item.model_dump()) == {"title", "url", "content", "media"}
        for item in result.composer_corpus()
    )
    assert result.run_audit.stage_timings_seconds["total"] >= 0


def test_run_uses_one_gap_query_to_cover_a_missing_angle() -> None:
    # Break caught: failing to recover a known coverage gap, running duplicate recovery searches, or
    # spending a separate LLM call on a recovery query the planner already wrote.
    plan = with_backup(make_plan(), "community solar adoption outcomes evidence")
    first = make_candidate("cost-page", "cost", "cost.example")
    second = make_candidate("policy-page", "policy", "policy.example")
    recovered = make_candidate("adoption-page", "gap-backup", "adoption.example")
    llm = FakeLLM(
        plan,
        {
            "evaluations": [
                evaluation(first.id, "cost"),
                evaluation(second.id, "policy"),
            ]
        },
        {"evaluations": [evaluation(recovered.id, "adoption")]},
    )
    search = FakeSearch(
        {
            "cost": [first],
            "policy": [second],
            "adoption": [],
            "gap-backup": [recovered],
        }
    )
    agent = make_agent(
        llm,
        search,
        FakeExtractor(
            {
                first.url: make_document(first),
                second.url: make_document(second),
                recovered.url: make_document(recovered),
            }
        ),
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.COMPLETE
    assert [query.id for query in search.calls].count("gap-backup") == 1
    assert search.calls[-1].query == "community solar adoption outcomes evidence"
    assert [call["role"] for call in llm.calls] == [
        "research_planning",
        "research_evaluation",
        "research_evaluation",
    ]
    assert result.run_audit.rejection_reasons["gap_recovery"] == "completed"
    assert result.run_audit.provider_usage["gap_planning"] == "planner_backup"
    assert result.run_audit.provider_usage["gap_query"] == "gap-backup"
    assert result.run_audit.gap_search_used is True


def test_run_never_repeats_a_failed_gap_recovery() -> None:
    # Break caught: recursively issuing a gap query when the one permitted recovery yields no usable pages.
    plan = with_backup(make_plan(), "community solar adoption evidence")
    first = make_candidate("cost-page", "cost", "cost.example")
    second = make_candidate("policy-page", "policy", "policy.example")
    llm = FakeLLM(
        plan,
        {
            "evaluations": [
                evaluation(first.id, "cost"),
                evaluation(second.id, "policy"),
            ]
        },
    )
    search = FakeSearch(
        {"cost": [first], "policy": [second], "adoption": [], "gap-backup": []}
    )
    agent = make_agent(
        llm,
        search,
        FakeExtractor(
            {first.url: make_document(first), second.url: make_document(second)}
        ),
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.LOW_COVERAGE
    assert [query.id for query in search.calls].count("gap-backup") == 1
    assert len(llm.calls) == 2
    assert result.run_audit.rejection_reasons["gap_recovery"] == "no_new_candidates"


@pytest.mark.parametrize(
    ("case", "backup", "persona", "brief_variant", "reason"),
    (
        (
            "backup only for a covered angle",
            BackupQuery(angle="cost", query="community solar cost benchmarks"),
            PersonaContext(),
            None,
            "no_backup_for_missing_angles",
        ),
        (
            "Unicode-normalized duplicate query",
            BackupQuery(
                angle="adoption",
                query="ＣＯＭＭＵＮＩＴＹ　ＳＯＬＡＲ　ＡＤＯＰＴＩＯＮ　ＤＡＴＡ",
            ),
            PersonaContext(),
            None,
            "backup_rejected: ValueError: gap query duplicates",
        ),
        (
            "backup emptied by planning clean-up",
            BackupQuery(angle="adoption", query="\u3000"),
            PersonaContext(),
            None,
            "no_backup_for_missing_angles",
        ),
        (
            "lost declared constraint",
            BackupQuery(angle="adoption", query="community solar adoption outcomes"),
            PersonaContext(),
            "declared_constraint",
            "backup_rejected: ValueError: gap query omitted",
        ),
        (
            "lost declared entity",
            BackupQuery(angle="adoption", query="adoption outcomes evidence"),
            PersonaContext(),
            "declared_entity",
            "backup_rejected: ValueError: gap query omitted",
        ),
    ),
)
def test_run_replaces_an_invalid_planner_backup_with_a_safe_local_query(
    case: str,
    backup: BackupQuery,
    persona: PersonaContext,
    brief_variant: str | None,
    reason: str,
) -> None:
    # Break caught: an unsafe or off-brief planner backup reaching search instead of a safe local recovery query.
    plan = make_plan()
    first = make_candidate("cost-page", "cost", "cost.example")
    second = make_candidate("policy-page", "policy", "policy.example")
    if brief_variant == "declared_constraint":
        brief = plan.brief.model_copy(
            update={"main_keywords": ("community solar",), "constraints": ("evidence",)}
        )
        queries = tuple(
            query.model_copy(update={"query": f"{query.query} evidence"})
            for query in plan.queries
        )
        plan = plan.model_copy(update={"brief": brief, "queries": queries})
    elif brief_variant == "declared_entity":
        brief = plan.brief.model_copy(update={"main_keywords": ("community solar",)})
        plan = plan.model_copy(update={"brief": brief})
    plan = plan.model_copy(update={"backup_queries": (backup,)})

    search = FakeSearch({"cost": [first], "policy": [second], "adoption": []})
    llm = FakeLLM(
        plan,
        {
            "evaluations": [
                evaluation(first.id, "cost"),
                evaluation(second.id, "policy"),
            ]
        },
    )
    agent = make_agent(
        llm,
        search,
        FakeExtractor(
            {first.url: make_document(first), second.url: make_document(second)}
        ),
    )

    result = run(agent.run("Research community solar", persona))

    assert result.status == ResearchStatus.LOW_COVERAGE, case
    assert {item.title for item in result.corpus} == {first.title, second.title}, case
    assert len(search.calls) == 4, case
    assert len(llm.calls) == 2, case
    assert search.calls[-1].id == "gap-fallback", case
    assert search.calls[-1].query.startswith("community solar adoption"), case
    assert (
        result.run_audit.provider_usage["gap_planning"] == "deterministic_fallback"
    ), case
    assert result.run_audit.rejection_reasons["gap_planning_fallback"].startswith(
        reason
    ), case
    assert result.run_audit.rejection_reasons["gap_recovery"] == "no_new_candidates", (
        case
    )


ML_CREATOR_BRIEF = ResearchBrief(
    topic="Social media post ideas for ML research, career hacks, and system design",
    main_keywords=("ML research", "career hacks", "system design"),
    user_goal="Generate engaging content ideas",
    required_angles=(
        "latest ML research trends",
        "practical career advice for engineers",
        "system design best practices",
    ),
    freshness_mode=FreshnessMode.RECENT,
    freshness_window_days=90,
)


@pytest.mark.parametrize(
    "backup_text",
    (
        "Instagram community solar adoption evidence",
        "Gen Z community solar adoption evidence",
    ),
)
def test_run_scrubs_persona_and_platform_labels_from_planner_backups_like_main_queries(
    backup_text: str,
) -> None:
    # Break caught: a planner backup carrying unrequested persona or platform labels into search.
    plan = with_backup(make_plan(), backup_text)
    first = make_candidate("cost-page", "cost", "cost.example")
    second = make_candidate("policy-page", "policy", "policy.example")
    search = FakeSearch(
        {"cost": [first], "policy": [second], "adoption": [], "gap-backup": []}
    )
    llm = FakeLLM(
        plan,
        {
            "evaluations": [
                evaluation(first.id, "cost"),
                evaluation(second.id, "policy"),
            ]
        },
    )
    agent = make_agent(
        llm,
        search,
        FakeExtractor(
            {first.url: make_document(first), second.url: make_document(second)}
        ),
    )

    result = run(
        agent.run("Research community solar", PersonaContext(audience="Gen Z"))
    )

    assert result.run_audit.provider_usage["gap_planning"] == "planner_backup"
    assert search.calls[-1].query == "community solar adoption evidence"


@pytest.mark.parametrize(
    ("query", "accepted"),
    (
        # A real LLM recovery query: one subject of three, spelled out instead of abbreviated.
        (
            "What are the most recent breakthroughs and emerging trends in machine learning research from the past 90 days?",
            True,
        ),
        (
            "What are the most recent breakthroughs and emerging trends in research from the past 90 days?",
            False,
        ),
    ),
)
def test_gap_lane_needs_one_main_keyword_not_every_subject_of_the_brief(
    query: str, accepted: bool
) -> None:
    # Break caught: a focused lane for "latest ML research trends" rejected for not also naming career
    # hacks and system design, and "machine learning" not counting as the keyword "ML research".
    lane = PlannedQuery(
        id="gap-backup",
        query=query,
        purpose="latest ML research trends",
        intent="news",
        freshness_window_days=90,
    )

    if accepted:
        ResearchAgent._validate_gap_query(lane, (), ML_CREATOR_BRIEF)
    else:
        with pytest.raises(ValueError, match="omitted brief main keywords"):
            ResearchAgent._validate_gap_query(lane, (), ML_CREATOR_BRIEF)


def test_run_records_attempted_gap_search_when_a_gap_provider_failure_returns_no_candidates() -> (
    None
):
    # Break caught: recording a failed attempt as skipped after the validated search has already started.
    plan = with_backup(make_plan(), "community solar adoption evidence")
    first = make_candidate("cost-page", "cost", "cost.example")
    second = make_candidate("policy-page", "policy", "policy.example")
    search = FakeSearch(
        {
            "cost": [first],
            "policy": [second],
            "adoption": [],
            "gap-backup": RuntimeError("search offline"),
        }
    )
    llm = FakeLLM(
        plan,
        {
            "evaluations": [
                evaluation(first.id, "cost"),
                evaluation(second.id, "policy"),
            ]
        },
    )
    agent = make_agent(
        llm,
        search,
        FakeExtractor(
            {first.url: make_document(first), second.url: make_document(second)}
        ),
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.LOW_COVERAGE
    assert result.run_audit.gap_search_used is True
    assert result.run_audit.rejection_reasons["query:gap-backup"] == "search_error"
    assert (
        result.run_audit.notes["query:gap-backup"]
        == "search_error: RuntimeError: search offline"
    )


def test_run_uses_a_local_gap_query_when_the_plan_has_no_backup() -> None:
    """Break caught: a plan without backups (e.g. the deterministic fallback plan) ending the only recovery pass."""
    plan = make_plan()
    first = make_candidate("cost-page", "cost", "cost.example")
    second = make_candidate("policy-page", "policy", "policy.example")
    search = FakeSearch({"cost": [first], "policy": [second], "adoption": []})
    llm = FakeLLM(
        plan,
        {
            "evaluations": [
                evaluation(first.id, "cost"),
                evaluation(second.id, "policy"),
            ]
        },
    )
    agent = make_agent(
        llm,
        search,
        FakeExtractor(
            {first.url: make_document(first), second.url: make_document(second)}
        ),
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.LOW_COVERAGE
    assert result.run_audit.gap_search_used is True
    assert len(llm.calls) == 2
    assert result.run_audit.provider_usage["gap_planning"] == "deterministic_fallback"
    assert (
        result.run_audit.rejection_reasons["gap_planning_fallback"]
        == "no_backup_for_missing_angles"
    )
    assert result.run_audit.rejection_reasons["gap_recovery"] == "no_new_candidates"
    assert search.calls[-1].purpose == "adoption"
    assert search.calls[-1].query == "community solar adoption"


def test_run_does_not_report_an_evaluation_provider_when_no_pages_were_evaluated() -> (
    None
):
    """Break caught: stale planner provenance being mislabeled as an evaluator call."""

    class ProviderAwareFakeLLM(FakeLLM):
        last_provider = "groq"

    result = run(
        make_agent(
            ProviderAwareFakeLLM(make_plan()),
            FakeSearch(),
            FakeExtractor(),
            max_gap_searches=0,
        ).run("Research community solar", PersonaContext())
    )

    assert result.run_audit.provider_usage["planning"] == "groq"
    assert "evaluation" not in result.run_audit.provider_usage


def test_run_records_attempted_gap_search_before_a_gap_timeout() -> None:
    # Break caught: an optional recovery timeout discarding a usable first-pass corpus or reporting search as skipped.
    class HangingGapSearch(FakeSearch):
        async def search(self, query, brief, max_results):
            if query.id == "gap-backup":
                await asyncio.Event().wait()
            return await super().search(query, brief, max_results)

    plan = with_backup(make_plan(), "community solar adoption evidence")
    first = make_candidate("cost-page", "cost", "cost.example")
    second = make_candidate("policy-page", "policy", "policy.example")
    agent = make_agent(
        FakeLLM(
            plan,
            {
                "evaluations": [
                    evaluation(first.id, "cost"),
                    evaluation(second.id, "policy"),
                ]
            },
        ),
        HangingGapSearch({"cost": [first], "policy": [second], "adoption": []}),
        FakeExtractor(
            {first.url: make_document(first), second.url: make_document(second)}
        ),
        search_timeout_seconds=0.2,
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.LOW_COVERAGE
    assert {item.title for item in result.corpus} == {first.title, second.title}
    assert {page.candidate.id for page in result.evaluated_pages} == {
        first.id,
        second.id,
    }
    assert result.run_audit.rejection_reasons["gap_recovery"] == "gap_search_timeout"
    assert result.run_audit.gap_search_used is True


def test_run_returns_typed_low_or_zero_coverage_results() -> None:
    # Break caught: treating weak/absent research evidence as a completed corpus.
    plan = with_backup(make_plan(), "community solar adoption evidence")
    first = make_candidate("cost-page", "cost", "cost.example")
    second = make_candidate("policy-page", "policy", "policy.example")
    two_page_agent = make_agent(
        FakeLLM(
            plan,
            {
                "evaluations": [
                    evaluation(first.id, "cost"),
                    evaluation(second.id, "policy"),
                ]
            },
        ),
        FakeSearch(
            {"cost": [first], "policy": [second], "adoption": [], "gap-backup": []}
        ),
        FakeExtractor(
            {first.url: make_document(first), second.url: make_document(second)}
        ),
    )
    empty_agent = make_agent(
        FakeLLM(plan),
        FakeSearch({"cost": [], "policy": [], "adoption": []}),
        FakeExtractor(),
    )

    partial = run(two_page_agent.run("Research community solar", PersonaContext()))
    empty = run(empty_agent.run("Research community solar", PersonaContext()))

    assert partial.status == ResearchStatus.LOW_COVERAGE
    assert len(partial.corpus) == 2
    assert empty.status == ResearchStatus.FAILED
    assert empty.error_type == "insufficient_coverage"
    assert empty.error_message == "insufficient_coverage"
    assert empty.corpus == ()


def test_run_recovers_from_planner_failure_and_keeps_partial_search_and_extraction_successes() -> (
    None
):
    # Break caught: a planner failure stopping before deterministic fallback queries reach search.
    planner_failure = make_agent(
        FakeLLM(RuntimeError("planner offline")), FakeSearch(), FakeExtractor()
    )
    plan = make_plan()
    good = make_candidate("cost-page", "cost", "cost.example")
    partial = make_agent(
        FakeLLM(plan, {"evaluations": [evaluation(good.id, "cost")]}),
        FakeSearch(
            {"cost": [good], "policy": RuntimeError("search offline"), "adoption": []}
        ),
        FakeExtractor({good.url: make_document(good)}),
    )

    failed = run(planner_failure.run("Research community solar", PersonaContext()))
    recovered_partial = run(partial.run("Research community solar", PersonaContext()))

    assert failed.status == ResearchStatus.FAILED
    assert failed.error_type == "insufficient_coverage"
    assert failed.error_message == "insufficient_coverage"
    assert failed.plan is not None
    assert len(failed.plan.queries) == 3
    assert failed.run_audit.provider_usage["planning"] == "deterministic_fallback"
    assert (
        failed.run_audit.rejection_reasons["planning_fallback"]
        == "provider_error: RuntimeError: planner offline"
    )
    assert recovered_partial.status == ResearchStatus.LOW_COVERAGE
    assert len(recovered_partial.corpus) == 1
    assert (
        recovered_partial.run_audit.rejection_reasons["query:policy"] == "search_error"
    )


def test_run_uses_local_plan_after_the_model_planning_deadline() -> None:
    """Break caught: a slow planner consuming its allowance and terminating before fallback search."""

    class SlowLLM(FakeLLM):
        async def structured(self, *args, **kwargs):
            await asyncio.sleep(0.05)
            return await super().structured(*args, **kwargs)

    agent = make_agent(
        SlowLLM(make_plan()),
        FakeSearch(),
        FakeExtractor(),
        planning_timeout_seconds=0.01,
        hard_timeout_seconds=1.0,
    )

    result = run(agent.run("Latest community solar news", PersonaContext()))

    assert result.error_type == ResearchErrorType.INSUFFICIENT_COVERAGE
    assert result.plan is not None
    assert len(result.plan.queries) == 3
    assert result.run_audit.provider_usage["planning"] == "deterministic_fallback"
    assert (
        result.run_audit.rejection_reasons["planning_fallback"]
        == "planning_timeout: local fallback used"
    )


def test_run_degrades_to_deterministic_ranking_when_the_evaluator_is_unavailable() -> (
    None
):
    # Break caught: an evaluator outage or rate limit discarding already-fetched, validated pages
    # and handing the composer nothing; or the degraded run being reported as complete.
    plan = make_plan()
    page = make_candidate("cost-page", "cost", "cost.example")
    agent = make_agent(
        FakeLLM(plan, RuntimeError("evaluator offline")),
        FakeSearch({"cost": [page], "policy": [], "adoption": []}),
        FakeExtractor({page.url: make_document(page)}),
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.LOW_COVERAGE
    assert result.error_type == "evaluation"
    assert result.error_message == "evaluation_degraded"
    assert result.run_audit.coverage_status == "evaluation_degraded"
    assert result.run_audit.provider_usage["evaluation"] == "deterministic_fallback"
    assert result.plan == plan
    assert result.search_results == (page,)
    assert len(result.corpus) == 1
    evaluated = result.evaluated_pages[0]
    assert evaluated.accepted
    assert evaluated.scores.authority == 5.0 and evaluated.scores.persona_utility == 5.0
    assert evaluated.scores.rationale.startswith("deterministic_fallback")


def test_run_labels_each_model_call_with_its_pipeline_stage() -> None:
    # Break caught: a stage forgetting its role and silently falling onto the default provider chain.
    plan = make_plan()
    pages = [
        make_candidate(f"{angle}-page", angle, f"{angle}.example")
        for angle in ("cost", "policy", "adoption")
    ]
    llm = FakeLLM(
        plan,
        {"evaluations": [evaluation(page.id, page.discovered_by[0]) for page in pages]},
    )
    agent = make_agent(
        llm,
        FakeSearch({page.discovered_by[0]: [page] for page in pages}),
        FakeExtractor({page.url: make_document(page) for page in pages}),
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.COMPLETE
    assert [call["role"] for call in llm.calls] == [
        "research_planning",
        "research_evaluation",
    ]


def test_run_fails_when_the_evaluator_is_unavailable_and_nothing_was_validated() -> (
    None
):
    # Break caught: the deterministic fallback inventing a corpus out of zero validated pages.
    plan = make_plan()
    page = make_candidate("cost-page", "cost", "cost.example")
    agent = make_agent(
        FakeLLM(plan, RuntimeError("evaluator offline")),
        FakeSearch({"cost": [page], "policy": [], "adoption": []}),
        FakeExtractor({page.url: RuntimeError("reader down")}),
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.FAILED
    assert result.corpus == ()


def test_run_preserves_partial_extraction_and_keeps_an_omitted_evaluation_id() -> None:
    # Break caught: extraction siblings being discarded, or a page the model skipped vanishing from the ranked set.
    plan = make_plan()
    cost = make_candidate("cost-page", "cost", "cost.example")
    policy = make_candidate("policy-page", "policy", "policy.example")
    adoption = make_candidate("adoption-page", "adoption", "adoption.example")
    llm = FakeLLM(
        plan,
        {"evaluations": [evaluation(cost.id, "cost")]},
        {"evaluations": [evaluation("unknown-page", "policy")]},
    )
    agent = make_agent(
        llm,
        FakeSearch({"cost": [cost], "policy": [policy], "adoption": [adoption]}),
        FakeExtractor(
            {
                cost.url: make_document(cost),
                policy.url: make_document(policy),
                adoption.url: ExtractionError(
                    adoption.id, "reader_unavailable", "reader unavailable"
                ),
            }
        ),
        max_gap_searches=0,
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.LOW_COVERAGE
    assert [page.candidate.id for page in result.evaluated_pages] == [
        cost.id,
        policy.id,
    ]
    missing = next(
        page for page in result.evaluated_pages if page.candidate.id == policy.id
    )
    # The omitted id is scored deterministically and kept, with a note rather than a rejection.
    assert missing.scores is not None
    assert missing.scores.rationale.startswith("deterministic_fallback")
    assert result.run_audit.rejection_reasons[adoption.url] == "reader_unavailable"
    assert policy.url not in result.run_audit.rejection_reasons
    assert (
        result.run_audit.notes[policy.url]
        == "evaluation_missing: deterministic score used"
    )
    assert len(llm.calls) == 2  # plan + one evaluation; no repair round-trip


def test_run_timeout_cancels_inflight_work_and_caller_cancellation_propagates() -> None:
    # Break caught: turning cancellation into an internal failure or leaving timed-out search tasks running.
    plan = make_plan()

    class HangingSearch:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.cancelled = 0

        async def search(self, query, brief, max_results) -> list[CandidatePage]:
            self.started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled += 1
                raise
            raise AssertionError("unreachable: the search hangs until it is cancelled")

    timeout_search = HangingSearch()
    timeout_agent = make_agent(
        FakeLLM(plan),
        timeout_search,
        FakeExtractor(),
        hard_timeout_seconds=0.2,
        search_timeout_seconds=30.0,
    )
    timeout_result = run(
        timeout_agent.run("Research community solar", PersonaContext())
    )

    async def caller_cancellation() -> None:
        search = HangingSearch()
        agent = make_agent(
            FakeLLM(plan), search, FakeExtractor(), hard_timeout_seconds=30.0
        )
        task = asyncio.create_task(
            agent.run("Research community solar", PersonaContext())
        )
        await search.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert search.cancelled >= 1

    run(caller_cancellation())

    assert timeout_result.status == ResearchStatus.TIMEOUT
    assert timeout_result.error_type == "timeout"
    assert timeout_result.error_message == "timeout"
    assert timeout_result.run_audit.rejection_reasons.get("gap_recovery") is None
    assert timeout_search.cancelled >= 1


def test_run_skips_gap_when_evaluation_reserve_cannot_fit() -> None:
    # Break caught: starting optional gap recovery after consuming the evaluator's reserved hard-time budget.
    class Clock:
        value = 0.0

        def __call__(self) -> float:
            return self.value

    class AdvancingLLM(FakeLLM):
        async def structured(self, *args, **kwargs):
            response = await super().structured(*args, **kwargs)
            if len(self.calls) == 2:
                clock.value = 9.5
            return response

    clock = Clock()
    plan = make_plan()
    first = make_candidate("cost-page", "cost", "cost.example")
    second = make_candidate("policy-page", "policy", "policy.example")
    search = FakeSearch({"cost": [first], "policy": [second], "adoption": []})
    agent = ResearchAgent(
        config=replace(CONFIG, minimum_article_chars=100, hard_timeout_seconds=10.0),
        llm=AdvancingLLM(
            plan,
            {
                "evaluations": [
                    evaluation(first.id, "cost"),
                    evaluation(second.id, "policy"),
                ]
            },
        ),
        search=search,
        extractor=FakeExtractor(
            {first.url: make_document(first), second.url: make_document(second)}
        ),
        now=lambda: NOW,
        monotonic=clock,
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.LOW_COVERAGE
    assert all(query.id != "gap-adoption" for query in search.calls)
    assert (
        result.run_audit.rejection_reasons["gap_recovery"] == "insufficient_time_budget"
    )
    assert result.run_audit.gap_search_used is False


def test_run_skips_gap_at_exact_required_recovery_reserve_boundary() -> None:
    # Break caught: beginning gap planning with zero time after the mandatory evaluator reserve, then timing out.
    class Clock:
        value = 0.0

        def __call__(self) -> float:
            return self.value

    class AdvancingLLM(FakeLLM):
        async def structured(self, *args, **kwargs):
            response = await super().structured(*args, **kwargs)
            if len(self.calls) == 2:
                clock.value = 12.0
            return response

    clock = Clock()
    plan = make_plan()
    first = make_candidate("cost-page", "cost", "cost.example")
    second = make_candidate("policy-page", "policy", "policy.example")
    search = FakeSearch({"cost": [first], "policy": [second], "adoption": []})
    llm = AdvancingLLM(
        plan,
        {
            "evaluations": [
                evaluation(first.id, "cost"),
                evaluation(second.id, "policy"),
            ]
        },
    )
    agent = ResearchAgent(
        config=replace(
            CONFIG,
            minimum_article_chars=100,
            hard_timeout_seconds=20.0,
            gap_min_remaining_seconds=8.0,
            evaluation_reserve_seconds=8.0,
        ),
        llm=llm,
        search=search,
        extractor=FakeExtractor(
            {first.url: make_document(first), second.url: make_document(second)}
        ),
        now=lambda: NOW,
        monotonic=clock,
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.LOW_COVERAGE
    assert (
        result.run_audit.rejection_reasons["gap_recovery"] == "insufficient_time_budget"
    )
    assert len(llm.calls) == 2
    assert all(query.id != "gap-adoption" for query in search.calls)


def test_run_records_nonnegative_monotonic_timings() -> None:
    # Break caught: wall-clock or negative stage metrics.
    class Clock:
        value = 0.0

        def __call__(self) -> float:
            return self.value

    class AdvancingLLM(FakeLLM):
        async def structured(self, *args, **kwargs):
            response = await super().structured(*args, **kwargs)
            clock.value += 1.0
            return response

    class AdvancingSearch(FakeSearch):
        async def search(self, *args, **kwargs):
            response = await super().search(*args, **kwargs)
            clock.value += 1.0
            return response

    class AdvancingExtractor(FakeExtractor):
        async def extract(self, *args, **kwargs):
            response = await super().extract(*args, **kwargs)
            clock.value += 1.0
            return response

    clock = Clock()
    plan = make_plan()
    pages = [
        make_candidate("cost-page", "cost", "cost.example"),
        make_candidate("policy-page", "policy", "policy.example"),
        make_candidate("adoption-page", "adoption", "adoption.example"),
    ]
    llm = AdvancingLLM(
        plan,
        {
            "evaluations": [
                evaluation(page.id, angle)
                for page, angle in zip(
                    pages, ("cost", "policy", "adoption"), strict=True
                )
            ]
        },
    )
    search = AdvancingSearch(
        {"cost": [pages[0]], "policy": [pages[1]], "adoption": [pages[2]]}
    )
    extractor = AdvancingExtractor({page.url: make_document(page) for page in pages})

    agent = ResearchAgent(
        config=replace(CONFIG, minimum_article_chars=100),
        llm=llm,
        search=search,
        extractor=extractor,
        now=lambda: NOW,
        monotonic=clock,
    )
    result = run(agent.run("Research community solar", PersonaContext()))

    timings = result.run_audit.stage_timings_seconds
    assert all(value >= 0 for value in timings.values())
    assert timings["total"] >= sum(
        value for name, value in timings.items() if name != "total"
    )


def test_run_recovery_reuses_first_pass_content_deduplication() -> None:
    # Break caught: a different recovery URL with the identical cleaned body being evaluated and delivered twice.
    plan = with_backup(make_plan(), "community solar adoption outcomes evidence")
    cost = make_candidate("cost-page", "cost", "cost.example")
    policy = make_candidate("policy-page", "policy", "policy.example")
    recovered = make_candidate("adoption-page", "gap-backup", "adoption.example")
    shared_content = "# Shared evidence\n\n" + (
        "Identical complete evidence body for duplicate detection. " * 25
    )
    shared_cost_document = ExtractedDocument(
        candidate_id=cost.id,
        content=shared_content,
        title=cost.title,
        extraction_provider="fake-reader",
        article_type="Article",
    )
    shared_recovered_document = shared_cost_document.model_copy(
        update={"candidate_id": recovered.id, "title": recovered.title}
    )
    llm = FakeLLM(
        plan,
        {
            "evaluations": [
                evaluation(cost.id, "cost"),
                evaluation(policy.id, "policy"),
            ]
        },
    )
    agent = make_agent(
        llm,
        FakeSearch(
            {
                "cost": [cost],
                "policy": [policy],
                "adoption": [],
                "gap-backup": [recovered],
            }
        ),
        FakeExtractor(
            {
                cost.url: shared_cost_document,
                policy.url: make_document(policy),
                recovered.url: shared_recovered_document,
            }
        ),
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.LOW_COVERAGE
    assert result.run_audit.rejection_reasons[recovered.url] == "duplicate_content"
    assert [page.candidate.id for page in result.evaluated_pages] == [
        cost.id,
        policy.id,
    ]
    assert {item.title for item in result.corpus} == {cost.title, policy.title}
    assert len(llm.calls) == 2


def test_run_accumulates_monotonic_shortlist_timing_across_recovery() -> None:
    # Break caught: recording a fabricated zero first-pass shortlist time and omitting the recovery pass entirely.
    class Clock:
        value = 0.0

        def __call__(self) -> float:
            return self.value

    clock = Clock()
    plan = with_backup(make_plan(), "community solar adoption outcomes evidence")
    cost = make_candidate("cost-page", "cost", "cost.example")
    policy = make_candidate("policy-page", "policy", "policy.example")
    recovered = make_candidate("adoption-page", "gap-backup", "adoption.example")
    agent = ResearchAgent(
        config=replace(CONFIG, minimum_article_chars=100),
        llm=FakeLLM(
            plan,
            {
                "evaluations": [
                    evaluation(cost.id, "cost"),
                    evaluation(policy.id, "policy"),
                ]
            },
            {"evaluations": [evaluation(recovered.id, "adoption")]},
        ),
        search=FakeSearch(
            {
                "cost": [cost],
                "policy": [policy],
                "adoption": [],
                "gap-backup": [recovered],
            }
        ),
        extractor=FakeExtractor(
            {page.url: make_document(page) for page in (cost, policy, recovered)}
        ),
        now=lambda: NOW,
        monotonic=clock,
    )
    shortlist = agent._shortlist

    def timed_shortlist(pages: list[CandidatePage], brief) -> list[CandidatePage]:
        clock.value += 0.25
        return shortlist(pages, brief)

    agent._shortlist = timed_shortlist

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.COMPLETE
    assert result.run_audit.stage_timings_seconds["shortlist"] == pytest.approx(0.5)


def test_run_handles_malformed_extraction_results_without_losing_valid_siblings() -> (
    None
):
    # Break caught: a malformed extractor value escaping the extraction stage as top-level internal_error.
    plan = make_plan()
    good = make_candidate("cost-page", "cost", "cost.example")
    malformed = make_candidate("policy-page", "policy", "policy.example")
    agent = make_agent(
        FakeLLM(plan, {"evaluations": [evaluation(good.id, "cost")]}),
        FakeSearch({"cost": [good], "policy": [malformed], "adoption": []}),
        FakeExtractor(
            {
                good.url: make_document(good),
                malformed.url: {"not": "an extracted document"},
            }
        ),
        max_gap_searches=0,
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.LOW_COVERAGE
    assert result.error_type == ResearchErrorType.INSUFFICIENT_COVERAGE
    assert [page.candidate.id for page in result.evaluated_pages] == [good.id]
    assert result.run_audit.rejection_reasons[malformed.url] == "validation_error"


def test_run_maps_only_malformed_extractions_to_validation_failure() -> None:
    # Break caught: returning untyped internal_error when no usable extraction can survive malformed provider output.
    plan = make_plan()
    malformed = make_candidate("cost-page", "cost", "cost.example")
    agent = make_agent(
        FakeLLM(plan),
        FakeSearch({"cost": [malformed], "policy": [], "adoption": []}),
        FakeExtractor({malformed.url: {"not": "an extracted document"}}),
        max_gap_searches=0,
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert result.status == ResearchStatus.FAILED
    assert result.error_type == ResearchErrorType.VALIDATION
    assert result.error_message == "validation_error"
    assert result.run_audit.rejection_reasons[malformed.url] == "validation_error"


def test_a_cancelled_search_query_is_recorded_as_a_search_error() -> None:
    # Break caught: gather(return_exceptions=True) returns a CancelledError (a
    # BaseException, not an Exception) as a result; it was iterated and misreported
    # as a TypeError.
    good = make_candidate("cost-page", "cost", "cost.example")
    agent = make_agent(
        FakeLLM(make_plan(), {"evaluations": [evaluation(good.id, "cost")]}),
        FakeSearch(
            {"cost": [good], "policy": asyncio.CancelledError(), "adoption": []}
        ),
        FakeExtractor({good.url: make_document(good)}),
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert (
        result.run_audit.notes.get("query:policy") == "search_error: CancelledError: "
    )


def test_a_run_never_closes_the_providers_it_was_given() -> None:
    # Break caught: an agent closing providers the worker shares across runs,
    # which would break every later run.
    llm, search, extractor = FakeLLM(make_plan()), FakeSearch(), FakeExtractor()

    run(
        make_agent(llm, search, extractor).run(
            "Research community solar", PersonaContext()
        )
    )

    assert not (llm.closed or search.closed or extractor.closed)


def test_a_rate_limit_while_planning_pauses_the_run_instead_of_the_offline_plan() -> (
    None
):
    # Break caught: hiding a rate limit behind the offline plan; the runtime must see
    # it to pause the run and resume it once quota is back.
    agent = make_agent(
        FakeLLM(RateLimitedError("groq: HTTP 429")), FakeSearch(), FakeExtractor()
    )

    with pytest.raises(RateLimitedError):
        run(agent.run("Research community solar", PersonaContext()))


def test_a_rate_limit_while_scoring_pages_pauses_the_run() -> None:
    first = make_candidate("cost-page", "cost", "cost.example")
    agent = make_agent(
        FakeLLM(
            make_plan(), NoProviderAvailableError("every provider is cooling down")
        ),
        FakeSearch({"cost": [first], "policy": [], "adoption": []}),
        FakeExtractor({first.url: make_document(first)}),
    )

    with pytest.raises(NoProviderAvailableError):
        run(agent.run("Research community solar", PersonaContext()))


def test_a_rate_limit_during_optional_gap_recovery_keeps_the_main_results() -> None:
    # Break caught: pausing (and later redoing) the whole research step for an
    # optional extra search; the main results are kept and the gap step is skipped.
    plan = with_backup(make_plan(), "community solar adoption outcomes evidence")
    first = make_candidate("cost-page", "cost", "cost.example")
    second = make_candidate("policy-page", "policy", "policy.example")
    recovered = make_candidate("adoption-page", "gap-backup", "adoption.example")
    agent = make_agent(
        FakeLLM(
            plan,
            {
                "evaluations": [
                    evaluation(first.id, "cost"),
                    evaluation(second.id, "policy"),
                ]
            },
            RateLimitedError("groq: HTTP 429"),
        ),
        FakeSearch(
            {
                "cost": [first],
                "policy": [second],
                "adoption": [],
                "gap-backup": [recovered],
            }
        ),
        FakeExtractor(
            {
                first.url: make_document(first),
                second.url: make_document(second),
                recovered.url: make_document(recovered),
            }
        ),
    )

    result = run(agent.run("Research community solar", PersonaContext()))

    assert {item.title for item in result.corpus} == {first.title, second.title}
    assert result.run_audit.rejection_reasons["gap_recovery"] == "gap_rate_limited"
