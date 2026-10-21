"""Offline regression corpus for planning useful, bounded research query lanes."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from app.agents.research_agents.agent import ResearchAgent
from app.agents.research_agents.models import (
    CandidatePage,
    ExtractedDocument,
    PersonaContext,
    RunAudit,
)
from tests.agents.research_agents.fakes import FakeExtractor, FakeLLM, FakeSearch

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "query_cases.json"


def _cases() -> list[dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


CASES = _cases()

EXPECTED_INTENT_CLASSES = frozenset(
    {
        "breaking news",
        "current trend",
        "annual/current-cycle festival",
        "current recommendation",
        "quantitative/data request",
        "how-to",
        "opinion landscape",
        "evergreen explanation",
        "location-specific request",
        "culturally constrained topic",
        "platform-specific research explicitly requested",
        "vague request requiring inferred angles",
    }
)

EXPECTED_CASE_NAMES = {
    "breaking news": "breaking_ai_uk_policy",
    "current trend": "current_trend_sustainable_fashion",
    "annual/current-cycle festival": "current_cycle_diwali",
    "current recommendation": "current_recommendation_aeropress_eur_budget",
    "quantitative/data request": "quantitative_india_solar_data",
    "how-to": "how_to_matcha",
    "opinion landscape": "opinion_landscape_remote_work",
    "evergreen explanation": "evergreen_explanation_quantum_computing",
    "location-specific request": "location_specific_bengaluru_metro",
    "culturally constrained topic": "cultural_constraint_renee_french_vegetarian",
    "platform-specific research explicitly requested": "explicit_platform_reddit_research",
    "vague request requiring inferred angles": "vague_request_inferred_angles",
}

REQUIRED_CASE_FIELDS = frozenset(
    {
        "name",
        "intent_class",
        "user_input",
        "current_date",
        "persona",
        "preserved_entities",
        "preserved_constraints",
        "expected_freshness_mode",
        "expected_freshness_window_days",
        "expected_required_angles",
        "expected_query_freshness",
        "query_anchor_lanes",
        "required_query_purposes",
        "forbidden_terms",
        "planner_response",
    }
)


def test_fixture_corpus_has_exact_required_intent_classes_and_typed_contract() -> None:
    """Break caught: deleting, relabelling, or underspecifying a required evaluation case."""
    assert len(CASES) == 12
    assert {case["intent_class"] for case in CASES} == EXPECTED_INTENT_CLASSES
    assert len({case["name"] for case in CASES}) == 12
    assert {case["intent_class"]: case["name"] for case in CASES} == EXPECTED_CASE_NAMES

    for case in CASES:
        assert set(case) == REQUIRED_CASE_FIELDS, case["name"]
        assert isinstance(case["name"], str) and case["name"]
        assert isinstance(case["user_input"], str) and case["user_input"]
        assert isinstance(case["current_date"], str) and datetime.fromisoformat(
            case["current_date"]
        )
        assert isinstance(case["persona"], dict)
        assert all(
            isinstance(value, str) and value for value in case["preserved_entities"]
        )
        assert all(
            isinstance(value, str) and value for value in case["preserved_constraints"]
        )
        assert isinstance(case["expected_freshness_mode"], str)
        assert case["expected_freshness_window_days"] is None or isinstance(
            case["expected_freshness_window_days"], int
        )
        assert all(
            isinstance(value, str) and value
            for value in case["expected_required_angles"]
        )
        assert isinstance(case["expected_query_freshness"], dict)
        assert all(
            isinstance(query_id, str) and isinstance(window, int)
            for query_id, window in case["expected_query_freshness"].items()
        )
        assert set(case["query_anchor_lanes"]) == set(case["preserved_entities"]) | set(
            case["preserved_constraints"]
        )
        assert all(
            isinstance(anchor, str)
            and isinstance(query_ids, list)
            and query_ids
            and all(isinstance(query_id, str) and query_id for query_id in query_ids)
            for anchor, query_ids in case["query_anchor_lanes"].items()
        )
        assert case["expected_required_angles"] == case["required_query_purposes"]
        assert isinstance(case["planner_response"], dict)
        assert isinstance(case["planner_response"]["brief"], dict)
        assert isinstance(case["planner_response"]["queries"], list)


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _normal(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _has_anchor(text: str, anchor: str) -> bool:
    """Match normalized anchors as Unicode-aware whole tokens or phrases."""
    pattern = re.escape(_normal(anchor)).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){pattern}(?!\w)", _normal(text)) is not None


def _currency_constraint_pattern(constraint: str) -> re.Pattern[str]:
    """Require the requested direction, currency symbol, and exact numeric value."""
    match = re.fullmatch(
        r"(under|over|at most|at least)\s+([€$£₹¥])\s*(\d+(?:\.\d+)?)",
        _normal(constraint),
    )
    assert match is not None, f"unsupported currency constraint fixture: {constraint!r}"
    comparator, currency, amount = match.groups()
    return re.compile(
        rf"(?<!\w){re.escape(comparator)}\s+{re.escape(currency)}\s*{re.escape(amount)}(?!(?:\w|[.,]\d|\s+\d))"
    )


def _plan(case: dict[str, Any]) -> tuple[Any, FakeLLM]:
    llm = FakeLLM(case["planner_response"])
    agent = ResearchAgent(
        llm=llm,
        search=FakeSearch(),
        extractor=FakeExtractor(),
    )
    return (
        _run(
            agent._plan(
                case["user_input"],
                PersonaContext.model_validate(case["persona"]),
                datetime.fromisoformat(case["current_date"]),
            )
        ),
        llm,
    )


def test_evaluation_harness_sanitizes_persona_contamination_before_search() -> None:
    """Break caught: a repairable persona leak reaches the returned plan or provider query."""
    case = next(case for case in CASES if case["name"] == "breaking_ai_uk_policy")
    bad_response = json.loads(json.dumps(case["planner_response"]))
    bad_response["queries"][0]["query"] += " Instagram"
    search = FakeSearch()
    agent = ResearchAgent(
        llm=FakeLLM(bad_response), search=search, extractor=FakeExtractor()
    )

    plan = _run(
        agent._plan(
            case["user_input"],
            PersonaContext.model_validate(case["persona"]),
            datetime.fromisoformat(case["current_date"]),
        )
    )
    _run(agent._search_plan(plan, RunAudit()))

    assert all("instagram" not in query.query.casefold() for query in plan.queries)
    assert all("instagram" not in query.query.casefold() for query in search.calls)


def test_currency_anchor_matcher_requires_direction_currency_and_exact_value() -> None:
    """Break caught: substring checks accepting a changed comparator, currency, or price cap."""
    matcher = _currency_constraint_pattern("under €100")

    assert matcher.search("AeroPress travel gear under €100")
    assert matcher.search("AeroPress travel gear under € 100")
    assert matcher.search("AeroPress travel gear under €100 today")
    assert matcher.search("AeroPress travel gear €100") is None
    assert matcher.search("AeroPress travel gear over €100") is None
    assert matcher.search("AeroPress travel gear under $100") is None
    assert matcher.search("AeroPress travel gear under €1000") is None
    assert matcher.search("AeroPress travel gear under €100.50") is None
    assert matcher.search("AeroPress travel gear under €100,000") is None
    assert matcher.search("AeroPress travel gear under €100 000") is None
    assert matcher.search("AeroPress travel gear under €100\u00a0000") is None
    assert matcher.search("AeroPress travel gear under €100\u202f000") is None


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_query_case_passes_real_plan_validation_and_preserves_its_contract(
    case: dict[str, Any],
) -> None:
    """Break caught: planner drops an anchor, temporal constraint, or distinct research lane."""
    plan, llm = _plan(case)
    brief = plan.brief
    queries = plan.queries
    query_by_id = {query.id: query for query in queries}
    query_text = " ".join(query.query for query in queries)
    normalized_query_text = _normal(query_text)

    assert tuple(case["preserved_entities"]) == brief.main_keywords, case["name"]
    assert tuple(case["preserved_constraints"]) == brief.constraints, case["name"]
    assert tuple(case["expected_required_angles"]) == brief.required_angles, case[
        "name"
    ]
    assert brief.freshness_mode.value == case["expected_freshness_mode"], case["name"]
    assert brief.freshness_window_days == case["expected_freshness_window_days"], case[
        "name"
    ]
    assert (
        f"date={datetime.fromisoformat(case['current_date']).date().isoformat()}"
        in llm.last_user_prompt
    ), case["name"]
    assert f'"audience":"{case["persona"]["audience"]}"' in llm.last_user_prompt, case[
        "name"
    ]
    assert 3 <= len(queries) <= 5, case["name"]
    assert brief.search_query_count == len(queries), case["name"]
    assert len({query.id for query in queries}) == len(queries), case["name"]
    assert len({_normal(query.query) for query in queries}) == len(queries), case[
        "name"
    ]
    assert len({query.purpose.casefold() for query in queries}) == len(queries), case[
        "name"
    ]
    assert len({query.intent.casefold() for query in queries}) >= 2, case["name"]
    purpose_to_queries = {}
    for query in queries:
        purpose_to_queries.setdefault(query.purpose, []).append(query)
    for angle in brief.required_angles:
        assert len(purpose_to_queries.get(angle, [])) == 1, (
            f"{case['name']}: required angle {angle!r} lacks one lane"
        )
        assert purpose_to_queries[angle][0].query, (
            f"{case['name']}: required angle {angle!r} has an empty lane"
        )
    expected_freshness = case["expected_query_freshness"]
    if expected_freshness:
        assert set(expected_freshness) == set(query_by_id), case["name"]
        for query_id, expected_window in expected_freshness.items():
            assert query_by_id[query_id].freshness_window_days == expected_window, (
                f"{case['name']}: {query_id} freshness"
            )
    else:
        assert all(query.freshness_window_days is None for query in queries), case[
            "name"
        ]
    for anchor, lane_ids in case["query_anchor_lanes"].items():
        assert _has_anchor(query_text, anchor), (
            f"{case['name']}: missing query anchor {anchor!r}"
        )
        for query_id in lane_ids:
            assert query_id in query_by_id, (
                f"{case['name']}: unknown anchor lane {query_id!r}"
            )
            assert _has_anchor(query_by_id[query_id].query, anchor), (
                f"{case['name']}: {query_id} missing Unicode-aware anchor {anchor!r}"
            )
    for forbidden in case["forbidden_terms"]:
        if not _has_anchor(case["user_input"], forbidden):
            assert not _has_anchor(normalized_query_text, forbidden), (
                f"{case['name']}: leaked {forbidden!r}"
            )

    if case["name"] == "current_recommendation_aeropress_eur_budget":
        matcher = _currency_constraint_pattern("under €100")
        for query_id in ("pricing",):
            assert matcher.search(query_by_id[query_id].query), (
                f"{case['name']}: {query_id} lost exact euro budget"
            )


def test_explicit_platform_case_preserves_user_requested_platform_only() -> None:
    """Break caught: platform guard rejects the platform the user asked to research."""
    case = next(
        case for case in CASES if case["name"] == "explicit_platform_reddit_research"
    )
    plan, _ = _plan(case)

    assert any("reddit" in query.query.casefold() for query in plan.queries)
    assert all("instagram" not in query.query.casefold() for query in plan.queries)


def test_fixture_plan_passes_original_brief_and_persona_to_evaluation_in_separate_scopes() -> (
    None
):
    """Break caught: persona replacing the original brief or influencing relevance outside persona utility."""
    case = next(case for case in CASES if case["name"] == "breaking_ai_uk_policy")
    plan, _ = _plan(case)
    persona = PersonaContext.model_validate(case["persona"])
    candidate = CandidatePage(
        id="boundary-page",
        url="https://example.test/ai-policy",
        canonical_url="https://example.test/ai-policy",
        publisher_domain="example.test",
        search_provider="fake",
        title="AI policy announcement",
        snippet="UK policy update.",
        search_rank=1,
    )
    document = ExtractedDocument(
        candidate_id=candidate.id,
        title=candidate.title,
        content="UK AI policy evidence.",
        extraction_provider="fake",
    )
    evaluator = FakeLLM(
        {
            "evaluations": [
                {
                    "candidate_id": candidate.id,
                    "relevance": 8,
                    "freshness": 8,
                    "authority": 8,
                    "content_quality": 8,
                    "persona_utility": 5,
                    "covered_angles": ["official announcement"],
                    "justification": "The page is relevant to the original policy brief.",
                }
            ]
        }
    )
    agent = ResearchAgent(llm=evaluator, search=FakeSearch(), extractor=FakeExtractor())

    _run(
        agent._evaluate_pages(
            plan.brief,
            persona,
            [(candidate, document, document.content, document.content)],
            RunAudit(),
        )
    )

    system = evaluator.calls[0]["system"]
    prompt = evaluator.last_user_prompt
    brief_block = re.search(
        r"<research_brief>\n(.*?)\n</research_brief>", prompt, flags=re.DOTALL
    )
    persona_block = re.search(
        r'<persona_context scoring_scope="only persona_utility">\n(.*?)\n</persona_context>',
        prompt,
        flags=re.DOTALL,
    )
    assert brief_block is not None and persona_block is not None
    assert plan.brief.user_goal in brief_block.group(1)
    assert "Instagram" not in brief_block.group(1)
    assert '"audience":"Gen Z"' in persona_block.group(1)
    assert "brief alone controls relevance" in system
    assert "only persona_utility" in system
