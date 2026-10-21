# Ported tests pass deliberately invalid values to prove validation rejects them.
# pyright: reportArgumentType=false
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.agents.research_agents.config import CONFIG, Config
from app.agents.research_agents.models import (
    BackupQuery,
    CandidatePage,
    EvaluatedPage,
    ExtractedDocument,
    FinalCorpus,
    FreshnessMode,
    PageRank,
    PageRankBatch,
    PageRankInput,
    PageScores,
    PersonaContext,
    PlannedQuery,
    ResearchBrief,
    ResearchPlan,
    ResearchResult,
    ResearchStatus,
    RunAudit,
)


def make_brief() -> ResearchBrief:
    return ResearchBrief(
        topic="solar power",
        main_keywords=("India",),
        user_goal="Create a factual explainer",
        required_angles=("policy", "cost"),
        language="en",
        freshness_mode=FreshnessMode.RECENT,
        freshness_window_days=30,
        constraints=("use primary sources",),
        search_query_count=3,
    )


def make_candidate() -> CandidatePage:
    return CandidatePage(
        id="page-1",
        url="https://news.example.com/article",
        canonical_url="https://news.example.com/article",
        publisher_domain="example.com",
        search_provider="tavily",
        title="Solar policy update",
        snippet="A substantive report about solar policy.",
        published_at=datetime(2026, 9, 1, tzinfo=UTC),
        discovered_by=("query-1",),
        search_rank=1,
    )


def make_plan() -> ResearchPlan:
    return ResearchPlan(
        brief=make_brief(),
        queries=(
            PlannedQuery(
                id="query-1",
                query="India solar policy update",
                purpose="policy",
                intent="news",
            ),
            PlannedQuery(
                id="query-2",
                query="India solar cost data",
                purpose="cost",
                intent="data",
            ),
            PlannedQuery(
                id="query-3",
                query="India solar capacity",
                purpose="capacity",
                intent="data",
            ),
        ),
    )


def test_composer_payload_contains_only_final_title_and_content() -> None:
    page = EvaluatedPage(
        candidate=make_candidate(),
        content="Complete cleaned article text.",
        ranking_view="Compact ranking view.",
        article_type="article",
        extraction_quality=0.9,
        scores=PageScores(
            relevance=9,
            freshness=8,
            authority=8,
            information_density=9,
            persona_utility=7,
            novelty=8,
        ),
        covered_angles=("policy",),
        accepted=True,
    )
    result = ResearchResult(
        corpus=(
            FinalCorpus(
                title="Solar policy update",
                content="Complete cleaned article text.",
                url="https://news.example.com/article",
                media=["path/to/images/photo.jpg"],
            ),
        ),
        brief=make_brief(),
        plan=make_plan(),
        evaluated_pages=(page,),
        run_audit=RunAudit(),
        status=ResearchStatus.COMPLETE,
    )
    assert result.composer_corpus() == [
        FinalCorpus(
            title="Solar policy update",
            content="Complete cleaned article text.",
            url="https://news.example.com/article",
            media=["path/to/images/photo.jpg"],
        )
    ]
    assert result.composer_corpus()[0].model_dump() == {
        "title": "Solar policy update",
        "url": "https://news.example.com/article",
        "content": "Complete cleaned article text.",
        "media": ["path/to/images/photo.jpg"],
    }


def test_internal_result_keeps_provenance_separate_from_composer_payload() -> None:
    candidate = make_candidate()
    result = ResearchResult(
        corpus=(
            FinalCorpus(
                title="Title",
                content="Body",
                url="https://news.example.com/article",
                media=["path/to/images/photo.jpg"],
            ),
        ),
        brief=make_brief(),
        plan=make_plan(),
        search_results=(candidate,),
        run_audit=RunAudit(provider_usage={"search": "tavily"}),
        status=ResearchStatus.LOW_COVERAGE,
        error_type="insufficient_coverage",
        error_message="Only one trustworthy page was found.",
    )

    assert result.search_results[0].url == "https://news.example.com/article"
    assert result.run_audit.provider_usage == {"search": "tavily"}
    assert result.composer_corpus()[0].model_dump().keys() == {
        "title",
        "url",
        "content",
        "media",
    }


def test_candidate_keeps_publisher_domain_distinct_from_search_provider() -> None:
    candidate = make_candidate()

    assert candidate.publisher_domain == "example.com"
    assert candidate.search_provider == "tavily"


def test_planned_query_does_not_accept_model_generated_confidence() -> None:
    with pytest.raises(ValidationError):
        PlannedQuery(
            id="query-1",
            query="India solar policy update",
            purpose="policy",
            intent="news",
            # Unknown field on purpose: the model must reject it.
            confidence=0.9,  # pyright: ignore[reportCallIssue]
        )


def test_research_result_can_truthfully_represent_a_planning_failure() -> None:
    result = ResearchResult(
        status=ResearchStatus.FAILED,
        error_type="planning",
        error_message="The planner returned invalid structured output.",
    )

    assert result.brief is None
    assert result.plan is None
    assert result.composer_corpus() == []


@pytest.mark.parametrize(
    "status", (ResearchStatus.COMPLETE, ResearchStatus.LOW_COVERAGE)
)
def test_successful_or_partial_results_require_brief_and_plan(
    status: ResearchStatus,
) -> None:
    with pytest.raises(ValidationError):
        ResearchResult(status=status)


def test_research_plan_rejects_duplicate_query_identifiers() -> None:
    repeated = PlannedQuery(
        id="query-1", query="India solar policy update", purpose="policy", intent="news"
    )

    with pytest.raises(ValidationError):
        ResearchPlan(
            brief=make_brief(),
            queries=(
                repeated,
                repeated,
                PlannedQuery(
                    id="query-3",
                    query="India solar capacity",
                    purpose="capacity",
                    intent="data",
                ),
            ),
        )


def test_planned_query_requires_a_stable_identifier_for_candidate_provenance() -> None:
    query = PlannedQuery(
        id="query-1", query="India solar policy update", purpose="policy", intent="news"
    )
    candidate = make_candidate()

    assert query.id == candidate.discovered_by[0]
    with pytest.raises(ValidationError):
        PlannedQuery(
            id="", query="India solar policy update", purpose="policy", intent="news"
        )


def test_public_supporting_contracts_model_persona_extraction_evaluation_and_gap_response() -> (
    None
):
    persona = PersonaContext(
        bio="Climate writer", niches=("energy",), audience="policy readers"
    )
    extracted = ExtractedDocument(
        candidate_id="page-1",
        content="Complete article body.",
        extraction_provider="jina",
    )
    evaluation_input = PageRankInput(
        candidate_id="page-1", title="Solar policy", ranking_view="Article summary"
    )
    evaluation = PageRank(
        candidate_id="page-1",
        relevance=9,
        freshness=8,
        authority=7,
        content_quality=8,
        persona_utility=7,
        covered_angles=("policy",),
        justification="Directly covers the policy angle.",
    )
    batch = PageRankBatch(evaluations=(evaluation,))
    plan = make_plan().model_copy(
        update={
            "backup_queries": (
                BackupQuery(angle="cost", query="India solar costs 2026"),
            )
        }
    )

    assert persona.niches == ("energy",)
    assert extracted.extraction_provider == "jina"
    assert evaluation_input.candidate_id == batch.evaluations[0].candidate_id
    assert batch.evaluations[0].content_quality == 8
    assert (
        ResearchPlan.model_validate(plan.model_dump()).backup_queries[0].angle == "cost"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("search_query_count", 2),
        ("search_query_count", 6),
        ("freshness_window_days", 0),
    ],
)
def test_research_brief_rejects_out_of_bounds_values(field: str, value: int) -> None:
    payload = make_brief().model_dump()
    payload[field] = value

    with pytest.raises(ValidationError):
        ResearchBrief(**payload)


def test_evergreen_brief_drops_any_freshness_window() -> None:
    # Break caught: a model answering "evergreen" with a 90-day window date-filtering a timeless search.
    payload = make_brief().model_dump()
    payload["freshness_mode"] = FreshnessMode.EVERGREEN

    assert ResearchBrief(**payload).freshness_window_days is None
    assert make_brief().freshness_window_days == 30


@pytest.mark.parametrize(
    "required_angles", ((), tuple(f"angle-{index}" for index in range(9)))
)
def test_research_brief_requires_a_bounded_nonempty_coverage_contract(
    required_angles: tuple[str, ...],
) -> None:
    # Break caught: allowing an empty or unbounded angle set makes coverage appear sufficient without evidence.
    payload = make_brief().model_dump()
    payload["required_angles"] = required_angles

    with pytest.raises(ValidationError):
        ResearchBrief(**payload)


def test_research_diagnostics_defaults_gap_search_to_not_attempted() -> None:
    # Break caught: a recovery attempt being reported when planning skipped or rejected it.
    assert RunAudit().gap_search_used is False


def test_config_uses_required_bounded_defaults() -> None:
    assert CONFIG.target_pages == 3
    assert CONFIG.max_pages == 4
    # Over-fetch: roughly a third of fetches fail, so the shortlist must be well above target.
    assert CONFIG.shortlist_size == 10 >= 3 * CONFIG.target_pages
    assert CONFIG.max_shortlist_size == 12 >= CONFIG.shortlist_size
    assert CONFIG.search_results_per_query == 3
    assert CONFIG.max_queries == 6
    assert CONFIG.min_queries == 3
    assert CONFIG.max_gap_searches == 1
    assert CONFIG.hard_timeout_seconds == 45.0
    assert CONFIG.planning_timeout_seconds == 10.0
    assert CONFIG.search_timeout_seconds == 10.0
    assert CONFIG.extraction_timeout_seconds == 18.0
    assert CONFIG.evaluation_timeout_seconds == 15.0
    assert CONFIG.evaluation_reserve_seconds == 8.0
    assert CONFIG.gap_min_remaining_seconds == 12.0
    assert CONFIG.search_concurrency == 5
    # One concurrent wave must cover the whole shortlist or extraction serialises past its cap.
    assert CONFIG.extract_concurrency == 10 >= CONFIG.shortlist_size
    assert CONFIG.page_extraction_timeout_seconds == 15.0
    assert CONFIG.max_download_bytes == 5_000_000
    assert CONFIG.max_clean_content_chars == 120_000
    assert CONFIG.ranking_view_chars == 2_400
    assert CONFIG.evaluation_view_char_budget == 16_000
    assert CONFIG.evaluation_view_min_chars == 600
    assert CONFIG.minimum_article_chars == 400
    assert {
        "youtube.com",
        "youtu.be",
    } <= CONFIG.blocked_domains  # video pages carry no article text
    assert CONFIG.max_missing_brief_anchors == 1
    assert CONFIG.max_missing_gap_declarations == 0
    with pytest.raises(ValueError, match="max_missing_brief_anchors"):
        Config(max_missing_brief_anchors=-1)
    assert CONFIG.cache_ttl_seconds == 21_600


def test_config_repr_never_exposes_provider_api_keys() -> None:
    config = Config(
        groq_api_key="groq-secret-sentinel",
        nvidia_api_key="nvidia-secret-sentinel",
        tavily_api_key="tavily-secret-sentinel",
    )

    rendered = repr(config)
    assert "groq-secret-sentinel" not in rendered
    assert "nvidia-secret-sentinel" not in rendered
    assert "tavily-secret-sentinel" not in rendered


def test_config_blocked_domains_are_immutable_and_no_public_searxng_fallback_exists() -> (
    None
):
    assert isinstance(CONFIG.blocked_domains, frozenset)
    assert Config(searxng_url="").searxng_url == ""
    assert not hasattr(CONFIG, "searxng_fallback_instances")
    assert not hasattr(CONFIG, "cerebras_api_key")
    # Mutations on purpose: the config must be immutable.
    with pytest.raises((AttributeError, TypeError)):
        CONFIG.blocked_domains.add("example.com")  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises((AttributeError, TypeError)):
        Config().blocked_domains = frozenset()  # pyright: ignore[reportAttributeAccessIssue]


def test_config_evaluation_policy_is_immutable_and_validated() -> None:
    # Floors mark unusable pages only; quality is decided by composite ranking.
    assert CONFIG.minimum_relevance_score == 3.0
    assert CONFIG.minimum_content_quality_score == 3.0
    assert CONFIG.minimum_composite_score == 3.0
    assert CONFIG.undated_freshness_multiplier == 0.7
    assert CONFIG.date_freshness_weight == 0.6
    with pytest.raises(ValueError, match="undated_freshness_multiplier"):
        Config(undated_freshness_multiplier=1.5)
    with pytest.raises(ValueError, match="date_freshness_weight"):
        Config(date_freshness_weight=-0.1)
    with pytest.raises(ValueError, match="max_shortlist_size"):
        Config(max_shortlist_size=0)


def test_config_draws_every_stage_from_one_groq_model_only() -> None:
    # Break caught: a run spending the second model's quota that other agents rely on, or a chain naming an unknown provider.
    assert (
        CONFIG.planning_provider_chain
        == CONFIG.evaluation_provider_chain
        == CONFIG.default_provider_chain
        == ("groq",)
    )
    assert CONFIG.groq_model == "openai/gpt-oss-120b"
    with pytest.raises(ValueError, match="evaluation_provider_chain"):
        Config(evaluation_provider_chain=("openai",))
    with pytest.raises(ValueError, match="must not repeat"):
        Config(planning_provider_chain=("groq", "groq"))
    with pytest.raises(ValueError, match="planning_provider_chain"):
        Config(planning_provider_chain=())
    assert (CONFIG.planning_reasoning_effort, CONFIG.evaluation_reasoning_effort) == (
        "medium",
        "low",
    )
    with pytest.raises(ValueError, match="evaluation_reasoning_effort"):
        Config(evaluation_reasoning_effort="max")
    assert isinstance(CONFIG.time_sensitive_score_weights, tuple)
    assert isinstance(CONFIG.evergreen_score_weights, tuple)
    assert sum(CONFIG.time_sensitive_score_weights) == pytest.approx(1.0)
    assert sum(CONFIG.evergreen_score_weights) == pytest.approx(1.0)

    with pytest.raises(ValueError, match="minimum_relevance_score"):
        Config(minimum_relevance_score=10.1)
    with pytest.raises(ValueError, match="exactly seven"):
        Config(time_sensitive_score_weights=(1.0,))
    with pytest.raises(ValueError, match="sum to 1"):
        Config(evergreen_score_weights=(0.2,) * 7)


def test_config_structural_and_optional_fourth_credibility_thresholds_are_validated() -> (
    None
):
    # Break caught: structural and optional-fourth quality gates relying on hidden or invalid local constants.
    assert CONFIG.minimum_structural_information_density == 3.60
    assert CONFIG.maximum_link_to_visible_text_ratio == 0.35
    assert CONFIG.maximum_navigation_footer_ratio == 0.50
    assert CONFIG.structural_penalty_floor == 0.25
    assert CONFIG.listing_body_penalty == 0.5
    with pytest.raises(ValueError, match="structural_penalty_floor"):
        Config(structural_penalty_floor=1.5)
    assert CONFIG.minimum_distinct_fourth_authority_score == 7.0
    assert CONFIG.minimum_distinct_fourth_content_quality_score == 7.0
    assert CONFIG.minimum_distinct_fourth_composite_score == 7.0

    with pytest.raises(ValueError, match="minimum_structural_information_density"):
        Config(minimum_structural_information_density=10.1)
    with pytest.raises(ValueError, match="maximum_link_to_visible_text_ratio"):
        Config(maximum_link_to_visible_text_ratio=1.1)
    with pytest.raises(ValueError, match="maximum_navigation_footer_ratio"):
        Config(maximum_navigation_footer_ratio=-0.1)
    with pytest.raises(ValueError, match="minimum_distinct_fourth_authority_score"):
        Config(minimum_distinct_fourth_authority_score=float("nan"))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("planning_timeout_seconds", 0),
        ("search_timeout_seconds", -1),
        ("extraction_timeout_seconds", float("inf")),
        ("page_extraction_timeout_seconds", 0),
        ("evaluation_timeout_seconds", float("nan")),
        ("evaluation_reserve_seconds", -1),
        ("gap_min_remaining_seconds", 0),
    ),
)
def test_config_rejects_non_positive_or_non_finite_pipeline_budgets(
    field: str, value: float
) -> None:
    with pytest.raises(ValueError, match=field):
        Config(**{field: value})


def test_config_requires_page_extraction_timeout_below_batch_timeout() -> None:
    with pytest.raises(ValueError, match="page_extraction_timeout_seconds"):
        Config(page_extraction_timeout_seconds=12.0, extraction_timeout_seconds=12.0)


def test_config_requires_gap_minimum_remaining_budget_to_cover_evaluation_reserve() -> (
    None
):
    # Break caught: accepting a recovery gate that can start despite an evaluator reserve that cannot fit.
    with pytest.raises(ValueError, match="gap_min_remaining_seconds"):
        Config(gap_min_remaining_seconds=7.99, evaluation_reserve_seconds=8.0)

    equal_boundary = Config(
        gap_min_remaining_seconds=8.0, evaluation_reserve_seconds=8.0
    )

    assert (
        equal_boundary.gap_min_remaining_seconds
        == equal_boundary.evaluation_reserve_seconds
    )
