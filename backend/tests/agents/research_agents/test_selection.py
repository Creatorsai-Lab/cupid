# Ported tests read optional scores that the test has already checked;
# pyright can't see those checks. To tighten later (plan: Later).
# pyright: reportOptionalMemberAccess=false, reportOptionalOperand=false, reportOperatorIssue=false


from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

import app.agents.research_agents.agent as agent_module
import app.agents.research_agents.filters as filters_module
from app.agents.research_agents.config import CONFIG
from app.agents.research_agents.models import (
    CandidatePage,
    EvaluatedPage,
    ExtractedDocument,
    FreshnessMode,
    PageScores,
    PersonaContext,
    ResearchBrief,
    RunAudit,
)
from app.agents.research_agents.providers import ExtractionError
from tests.agents.research_agents.fakes import FakeExtractor, FakeLLM, FakeSearch

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)


def run(coro):
    return asyncio.run(coro)


def brief(mode: FreshnessMode = FreshnessMode.EVERGREEN) -> ResearchBrief:
    return ResearchBrief(
        topic="community solar",
        main_keywords=("Solar Cooperative",),
        user_goal="Explain the evidence and practical tradeoffs",
        required_angles=("cost", "policy", "adoption", "outcomes"),
        freshness_mode=mode,
        freshness_window_days=30 if mode != FreshnessMode.EVERGREEN else None,
    )


def candidate(
    identifier: str,
    domain: str,
    *,
    published_at: datetime | None = NOW,
) -> CandidatePage:
    url = f"https://{domain}/reports/{identifier}"
    return CandidatePage(
        id=identifier,
        url=url,
        canonical_url=url,
        publisher_domain=domain,
        search_provider="tavily",
        title=f"Community solar report {identifier}",
        snippet="Evidence about community solar costs, policy, adoption, and outcomes.",
        published_at=published_at,
        discovered_by=("cost",),
        search_rank=1,
    )


def document(
    page: CandidatePage,
    *,
    content: str | None = None,
    published_at: datetime | None = None,
    article_type: str | None = "Article",
    metadata: dict | None = None,
) -> ExtractedDocument:
    return ExtractedDocument(
        candidate_id=page.id,
        content=content or ("Community solar evidence with substantive details. " * 30),
        title=page.title,
        published_at=published_at,
        extraction_provider="fake-reader",
        article_type=article_type,
        metadata=metadata or {},
    )


def substantive_article(subject: str) -> str:
    """Return varied prose for extraction tests that are not testing repetition quality gates."""
    return f"""# {subject} evidence report

The report defines its scope, records the collection period, and separates verified records from preliminary leads.
Researchers compared municipal filings, programme budgets, household surveys, and grid connection data before drawing conclusions.

## Methods

Analysts checked source publication dates, reconciled inconsistent totals, and documented exclusions that could affect interpretation.
Independent reviewers examined the sampling approach and published the assumptions used for every calculation.

## Findings

Installation costs changed differently across districts because procurement rules, financing terms, and available land varied.
Cooperatives reported that outreach improved participation when local advisers explained eligibility in plain language.
Grid operators identified connection queues as a practical constraint, while regulators described the safeguards used to monitor delivery.

## Limitations

The evidence does not claim that one intervention explains every outcome, and it identifies the data that remains incomplete.
Readers can trace each recommendation to a cited record, a stated assumption, or a directly observed implementation result.
"""


def evaluation(
    identifier: str,
    *,
    relevance: float = 8,
    freshness: float = 8,
    authority: float = 8,
    content_quality: float = 8,
    persona_utility: float = 5,
    covered_angles: tuple[str, ...] = ("cost",),
) -> dict:
    return {
        "candidate_id": identifier,
        "relevance": relevance,
        "freshness": freshness,
        "authority": authority,
        "content_quality": content_quality,
        "persona_utility": persona_utility,
        "covered_angles": list(covered_angles),
        "justification": f"Evidence-based evaluation for {identifier}.",
    }


def validated(page: CandidatePage, doc: ExtractedDocument | None = None):
    extracted = doc or document(page)
    content = extracted.content
    return page, extracted, content, content[:180]


def scored_page(
    identifier: str,
    domain: str,
    composite: float,
    angles: tuple[str, ...],
    *,
    published_at: datetime | None = NOW,
    accepted: bool = True,
    authority: float = 8,
    content_quality: float = 8,
) -> EvaluatedPage:
    page = candidate(identifier, domain, published_at=published_at)
    return EvaluatedPage(
        candidate=page,
        content="Complete accepted article content.",
        ranking_view="Compact view.",
        article_type="Article",
        extraction_quality=0.9,
        scores=PageScores(
            relevance=8,
            freshness=8,
            authority=authority,
            information_density=8,
            persona_utility=5,
            novelty=8,
            content_quality=content_quality,
            composite=composite,
            rationale="Strong evidence.",
        ),
        covered_angles=angles,
        accepted=accepted,
        rejection_reason=None if accepted else "test_rejection",
    )


def test_extract_valid_pages_runs_concurrently_and_isolates_failure() -> None:
    # Break caught: serial extraction, or one provider exception aborting useful pages.
    pages = [
        candidate("a", "alpha.example"),
        candidate("b", "beta.example"),
        candidate("c", "gamma.example"),
    ]
    running = 0
    peak = 0

    class ConcurrentExtractor:
        async def extract(self, page):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.01)
            running -= 1
            if page.id == "b":
                raise RuntimeError("reader unavailable")
            return document(page, content=substantive_article(page.id))

    extractor = ConcurrentExtractor()
    config = replace(CONFIG, extract_concurrency=3, minimum_article_chars=100)
    research_agent = agent_module.ResearchAgent(
        config=config,
        llm=FakeLLM(),
        search=FakeSearch(),
        extractor=extractor,
        now=lambda: NOW,
    )
    diagnostics = RunAudit()

    results = run(research_agent._extract_valid_pages(pages, brief(), diagnostics))

    assert peak >= 2
    assert [item[0].id for item in results] == ["a", "c"]
    assert diagnostics.rejection_reasons[pages[1].url] == "extraction_error"


def test_extract_valid_pages_keeps_fast_results_when_one_page_times_out() -> None:
    # Break caught: one slow reader making the all-or-nothing batch discard completed article pages.
    pages = [candidate(str(index), f"source-{index}.example") for index in range(6)]

    class OneSlowExtractor:
        async def extract(self, page):
            if page.id == "5":
                await asyncio.sleep(0.15)
            else:
                await asyncio.sleep(0.001)
            return document(page, content=substantive_article(page.id))

    config = replace(
        CONFIG,
        extract_concurrency=6,
        page_extraction_timeout_seconds=0.05,
        minimum_article_chars=100,
    )
    diagnostics = RunAudit()
    research_agent = agent_module.ResearchAgent(
        config=config,
        llm=FakeLLM(),
        search=FakeSearch(),
        extractor=OneSlowExtractor(),
        now=lambda: NOW,
    )

    results = run(research_agent._extract_valid_pages(pages, brief(), diagnostics))

    assert [item[0].id for item in results] == ["0", "1", "2", "3", "4"]
    assert diagnostics.rejection_reasons[pages[5].url] == "extraction_timeout"


def test_extract_valid_pages_keeps_listing_like_body_with_a_recorded_structural_note() -> (
    None
):
    # Break caught: a listing-shaped page being discarded before ranking, or passing with no trace of the weakness.
    page = candidate("listing", "alpha.example")
    cards = "\n\n".join(
        f"## Story {number}\nA short teaser. [Read more](https://alpha.example/{number})"
        for number in range(20)
    )
    research_agent = agent_module.ResearchAgent(
        config=replace(CONFIG, minimum_article_chars=100),
        llm=FakeLLM(),
        search=FakeSearch(),
        extractor=FakeExtractor({page.url: document(page, content=cards)}),
    )
    diagnostics = RunAudit()

    results = run(research_agent._extract_valid_pages([page], brief(), diagnostics))

    assert [item[0].id for item in results] == ["listing"]
    assert page.url not in diagnostics.rejection_reasons
    assert "listing_body" in diagnostics.notes[page.url]


def test_extract_valid_pages_keeps_undated_time_sensitive_page_and_rejects_known_stale_page() -> (
    None
):
    # Break caught: "no date found" being treated as "stale" and discarding fetchable, on-topic evidence.
    undated = candidate("undated", "alpha.example", published_at=None)
    stale = candidate("stale", "beta.example", published_at=NOW - timedelta(days=45))
    research_agent = agent_module.ResearchAgent(
        config=replace(CONFIG, minimum_article_chars=100),
        llm=FakeLLM(),
        search=FakeSearch(),
        extractor=FakeExtractor(
            {
                undated.url: document(undated, content=substantive_article("undated")),
                stale.url: document(stale, content=substantive_article("stale")),
            }
        ),
        now=lambda: NOW,
    )
    diagnostics = RunAudit()

    results = run(
        research_agent._extract_valid_pages(
            [undated, stale], brief(FreshnessMode.RECENT), diagnostics
        )
    )

    assert [item[0].id for item in results] == ["undated"]
    assert diagnostics.rejection_reasons[stale.url] == "stale"
    assert diagnostics.notes[undated.url] == "freshness_unknown"


def test_extract_valid_pages_rejects_metadata_language_mismatch() -> None:
    # Break caught: ignoring an extractor's explicit language mismatch.
    page = candidate("french-metadata", "alpha.example")
    research_agent = agent_module.ResearchAgent(
        config=replace(CONFIG, minimum_article_chars=100),
        llm=FakeLLM(),
        search=FakeSearch(),
        extractor=FakeExtractor(
            {
                page.url: document(
                    page,
                    content=("French source details. " * 30),
                    metadata={"language": "fr"},
                )
            }
        ),
    )
    diagnostics = RunAudit()

    assert run(research_agent._extract_valid_pages([page], brief(), diagnostics)) == []
    assert diagnostics.rejection_reasons[page.url] == "wrong_language"


def test_extract_valid_pages_rejects_clear_non_english_content_without_metadata() -> (
    None
):
    # Break caught: Jina/Trafilatura commonly omit language metadata, letting obvious Spanish text reach evaluation.
    page = candidate("spanish-body", "alpha.example")
    spanish = (
        "Este artículo explica los costos de la energía solar y las políticas públicas. "
        * 30
    )
    research_agent = agent_module.ResearchAgent(
        config=replace(CONFIG, minimum_article_chars=100),
        llm=FakeLLM(),
        search=FakeSearch(),
        extractor=FakeExtractor({page.url: document(page, content=spanish)}),
    )
    diagnostics = RunAudit()

    assert run(research_agent._extract_valid_pages([page], brief(), diagnostics)) == []
    assert diagnostics.rejection_reasons[page.url] == "wrong_language"


@pytest.mark.parametrize(
    ("identifier", "body"),
    (
        (
            "greek-body",
            "Αυτό το άρθρο εξηγεί το κόστος της ηλιακής ενέργειας και τη δημόσια πολιτική. "
            * 30,
        ),
        (
            "hebrew-body",
            "מאמר זה מסביר את עלויות האנרגיה הסולארית ואת המדיניות הציבורית. " * 30,
        ),
        ("thai-body", "บทความนี้อธิบายต้นทุนพลังงานแสงอาทิตย์และนโยบายสาธารณะอย่างละเอียด " * 30),
    ),
    ids=("greek", "hebrew", "thai"),
)
def test_extract_valid_pages_rejects_dominant_incompatible_scripts_without_metadata(
    identifier: str, body: str
) -> None:
    # Break caught: narrow non-Latin ranges missing common scripts in metadata-free extraction output.
    page = candidate(identifier, "alpha.example")
    research_agent = agent_module.ResearchAgent(
        config=replace(CONFIG, minimum_article_chars=100),
        llm=FakeLLM(),
        search=FakeSearch(),
        extractor=FakeExtractor({page.url: document(page, content=body)}),
    )
    diagnostics = RunAudit()

    assert run(research_agent._extract_valid_pages([page], brief(), diagnostics)) == []
    assert diagnostics.rejection_reasons[page.url] == "wrong_language"


def test_extract_valid_pages_rejects_incompatible_script_for_requested_hebrew() -> None:
    # Break caught: treating all non-English requested languages as compatible with every script.
    page = candidate("greek-for-hebrew", "alpha.example")
    greek = (
        "Αυτό το άρθρο εξηγεί το κόστος της ηλιακής ενέργειας και τη δημόσια πολιτική. "
        * 30
    )
    research_agent = agent_module.ResearchAgent(
        config=replace(CONFIG, minimum_article_chars=100),
        llm=FakeLLM(),
        search=FakeSearch(),
        extractor=FakeExtractor({page.url: document(page, content=greek)}),
    )
    diagnostics = RunAudit()

    assert (
        run(
            research_agent._extract_valid_pages(
                [page], brief().model_copy(update={"language": "he"}), diagnostics
            )
        )
        == []
    )
    assert diagnostics.rejection_reasons[page.url] == "wrong_language"


def test_extract_valid_pages_preserves_typed_provider_error_codes() -> None:
    # Break caught: flattening stable provider failure codes into a generic extraction error.
    typed = candidate("typed", "alpha.example")
    coded_but_untyped = candidate("coded-but-untyped", "gamma.example")
    untyped = candidate("untyped", "beta.example")

    class CodedButUntypedError(RuntimeError):
        code = "unsafe_redirect"

    research_agent = agent_module.ResearchAgent(
        llm=FakeLLM(),
        search=FakeSearch(),
        extractor=FakeExtractor(
            {
                typed.url: ExtractionError(
                    typed.id, "unsafe_redirect", "redirect reached a private host"
                ),
                coded_but_untyped.url: CodedButUntypedError(
                    "not a provider extraction error"
                ),
                untyped.url: RuntimeError("reader unavailable"),
            }
        ),
    )
    diagnostics = RunAudit()

    assert (
        run(
            research_agent._extract_valid_pages(
                [typed, coded_but_untyped, untyped], brief(), diagnostics
            )
        )
        == []
    )
    assert diagnostics.rejection_reasons[typed.url] == "unsafe_redirect"
    assert diagnostics.rejection_reasons[coded_but_untyped.url] == "extraction_error"
    assert diagnostics.rejection_reasons[untyped.url] == "extraction_error"


def test_extract_valid_pages_merges_page_date_only_when_search_date_is_absent() -> None:
    # Break caught: losing useful page metadata or overwriting known search provenance with a conflicting date.
    extracted_date = NOW - timedelta(days=2)
    search_date = NOW - timedelta(days=5)
    undated = candidate("undated", "alpha.example", published_at=None)
    dated = candidate("dated", "beta.example", published_at=search_date)
    extractor = FakeExtractor(
        {
            undated.url: document(
                undated,
                content=substantive_article("undated"),
                published_at=extracted_date,
            ),
            dated.url: document(
                dated, content=substantive_article("dated"), published_at=extracted_date
            ),
        }
    )
    research_agent = agent_module.ResearchAgent(
        config=replace(CONFIG, minimum_article_chars=100),
        llm=FakeLLM(),
        search=FakeSearch(),
        extractor=extractor,
        now=lambda: NOW,
    )

    results = run(
        research_agent._extract_valid_pages([undated, dated], brief(), RunAudit())
    )

    assert results[0][0].published_at == extracted_date
    assert results[1][0].published_at == search_date


def test_extract_valid_pages_keeps_complete_cleaned_content_separate_from_bounded_view() -> (
    None
):
    # Break caught: truncating the final article in place to make the evaluator prompt smaller.
    page = candidate("complete", "alpha.example")
    raw = "Title: Complete report\nMarkdown Content:\n\n" + substantive_article(
        "Community solar — café"
    )
    expected = filters_module.clean_article_content(raw)
    research_agent = agent_module.ResearchAgent(
        config=replace(CONFIG, minimum_article_chars=100, ranking_view_chars=180),
        llm=FakeLLM(),
        search=FakeSearch(),
        extractor=FakeExtractor({page.url: document(page, content=raw)}),
    )

    result = run(research_agent._extract_valid_pages([page], brief(), RunAudit()))[0]

    assert result[2] == expected
    assert len(result[2]) > 180
    assert len(result[3]) <= 180
    assert result[2].endswith("a directly observed implementation result.")


def test_evaluate_pages_shrinks_per_page_views_to_fit_the_batch_character_budget() -> (
    None
):
    # Break caught: a full shortlist producing an evaluator request above the provider's per-minute
    # token quota, so the whole evaluation stage fails instead of trading view depth for breadth.
    pages = [candidate(str(index), f"source-{index}.example") for index in range(6)]
    long_article = "\n\n".join(
        f"## Community solar cost and policy section {number}\n\n"
        f"Adoption outcomes for community solar cooperatives in district {number} depend on cost, policy "
        f"and grid access; this paragraph records the verified evidence and its limitations in detail."
        for number in range(1, 60)
    )
    validated_pages = [
        validated(page, document(page, content=long_article)) for page in pages
    ]
    validated_pages = [
        (c, d, content, filters_module.build_ranking_view(content, brief(), 4_000))
        for c, d, content, _ in validated_pages
    ]
    assert all(len(item[3]) > 1_500 for item in validated_pages)
    llm = FakeLLM({"evaluations": [evaluation(page.id) for page in pages]})
    research_agent = agent_module.ResearchAgent(
        config=replace(
            CONFIG,
            ranking_view_chars=4_000,
            evaluation_view_char_budget=6_000,
            evaluation_view_min_chars=200,
        ),
        llm=llm,
        search=FakeSearch(),
        extractor=FakeExtractor(),
        now=lambda: NOW,
    )

    results = run(
        research_agent._evaluate_pages(
            brief(), PersonaContext(), validated_pages, RunAudit()
        )
    )

    prompt = llm.last_user_prompt
    blocks = prompt.split("<untrusted_page candidate_id=")[1:]
    assert len(blocks) == 6
    assert all(len(block) < 1_500 for block in blocks)
    assert '<required_candidate_ids count="6">' in prompt
    # The stored article and full ranking view are untouched; only the prompt view shrank.
    assert all(len(page.content) == len(long_article) for page in results)
    assert all(len(page.ranking_view) > 1_500 for page in results)


def test_deterministic_evaluation_ranks_by_lexical_relevance_date_and_structure() -> (
    None
):
    # Break caught: the fallback scoring every page identically, or claiming judgement it cannot make.
    on_topic = candidate(
        "on-topic", "alpha.example", published_at=NOW - timedelta(days=1)
    )
    off_topic = candidate("off-topic", "beta.example", published_at=None)
    research_agent = agent_module.ResearchAgent(
        config=replace(CONFIG, minimum_article_chars=100),
        llm=FakeLLM(),
        search=FakeSearch(),
        extractor=FakeExtractor(),
        now=lambda: NOW,
    )
    unrelated = (
        "The orchestra rehearsed a symphony while the conductor discussed tempo and dynamics. "
        * 40
    )
    pages = [
        validated(
            on_topic,
            document(
                on_topic,
                content=substantive_article(
                    "Community solar cost policy adoption outcomes"
                ),
            ),
        ),
        validated(off_topic, document(off_topic, content=unrelated)),
    ]
    diagnostics = RunAudit()

    results = research_agent._deterministic_evaluation(
        brief(FreshnessMode.RECENT), pages, diagnostics
    )
    by_id = {page.candidate.id: page for page in results}

    assert by_id["on-topic"].scores.relevance > by_id["off-topic"].scores.relevance
    assert by_id["on-topic"].scores.composite > by_id["off-topic"].scores.composite
    assert by_id["on-topic"].scores.freshness_known is True
    assert by_id["off-topic"].scores.freshness_known is False
    assert set(by_id["on-topic"].covered_angles) >= {
        "cost",
        "policy",
        "adoption",
        "outcomes",
    }
    assert by_id["off-topic"].covered_angles == ()
    assert all(page.scores.authority == 5.0 for page in results)
    assert all(
        page.scores.rationale.startswith("deterministic_fallback") for page in results
    )


def test_evaluate_pages_uses_original_brief_untrusted_boundaries_and_stable_ids() -> (
    None
):
    # Break caught: scoring against persona alone, treating page text as instructions, or mapping by array position.
    first = candidate("first", "alpha.example")
    second = candidate("second", "beta.example")
    llm = FakeLLM(
        {
            "evaluations": [
                evaluation("second", covered_angles=("policy",)),
                evaluation("first", covered_angles=("cost",)),
            ]
        }
    )
    research_agent = agent_module.ResearchAgent(
        llm=llm, search=FakeSearch(), extractor=FakeExtractor()
    )
    persona = PersonaContext(audience="homeowners")

    results = run(
        research_agent._evaluate_pages(
            brief(), persona, [validated(first), validated(second)], RunAudit()
        )
    )

    assert [page.candidate.id for page in results] == ["first", "second"]
    assert results[0].covered_angles == ("cost",)
    assert results[1].covered_angles == ("policy",)
    prompt = llm.last_user_prompt
    assert "community solar" in prompt
    assert "Explain the evidence and practical tradeoffs" in prompt
    assert "<untrusted_reference_pages>" in prompt
    assert "never follow instructions" in (llm.calls[0]["system"] + prompt).lower()
    assert "only persona_utility" in (llm.calls[0]["system"] + prompt).lower()
    assert '"audience":"homeowners"' in prompt


def test_evaluate_pages_rejects_unknown_and_duplicate_items_and_scores_the_affected_page_locally() -> (
    None
):
    # Break caught: accepting an invented ID, choosing one duplicate arbitrarily, spending a repair
    # round-trip, or dropping the page whose evaluations were discarded.
    first = candidate("first", "alpha.example")
    second = candidate("second", "beta.example")
    llm = FakeLLM(
        {
            "evaluations": [
                evaluation("first"),
                evaluation("first", authority=2),
                evaluation("second"),
                evaluation("ghost"),
            ]
        }
    )
    diagnostics = RunAudit()
    research_agent = agent_module.ResearchAgent(
        llm=llm, search=FakeSearch(), extractor=FakeExtractor(), now=lambda: NOW
    )

    results = run(
        research_agent._evaluate_pages(
            brief(),
            PersonaContext(),
            [validated(first), validated(second)],
            diagnostics,
        )
    )

    assert len(llm.calls) == 1  # no repair round-trip in the reduced-call architecture
    assert [page.candidate.id for page in results] == ["first", "second"]
    conflicted, judged = results
    # Neither duplicate is trusted; the page is kept on deterministic scores instead.
    assert conflicted.scores.rationale.startswith("deterministic_fallback")
    assert conflicted.scores.authority == 5.0
    assert judged.covered_angles == ("cost",)
    assert judged.scores.rationale == "Evidence-based evaluation for second."
    assert (
        diagnostics.rejection_reasons["evaluation:unknown:ghost"]
        == "unknown_evaluation_id"
    )
    assert (
        diagnostics.rejection_reasons["evaluation:duplicate:first"]
        == "duplicate_evaluation_id"
    )
    assert (
        diagnostics.notes[first.url] == "evaluation_missing: deterministic score used"
    )


def test_evaluate_pages_scores_an_omitted_id_deterministically_instead_of_discarding_it() -> (
    None
):
    # Break caught: a fetched, validated page vanishing because the model skipped its id, or that page
    # receiving model-grade scores it never earned.
    first = candidate("first", "alpha.example")
    second = candidate("second", "beta.example")
    llm = FakeLLM({"evaluations": [evaluation("first")]})
    diagnostics = RunAudit()
    research_agent = agent_module.ResearchAgent(
        llm=llm, search=FakeSearch(), extractor=FakeExtractor(), now=lambda: NOW
    )

    results = run(
        research_agent._evaluate_pages(
            brief(),
            PersonaContext(),
            [validated(first), validated(second)],
            diagnostics,
        )
    )

    assert len(llm.calls) == 1  # no repair round-trip
    assert [page.candidate.id for page in results] == ["first", "second"]
    judged, missing = results
    assert judged.scores.rationale == "Evidence-based evaluation for first."
    assert missing.scores is not None
    assert missing.scores.rationale.startswith("deterministic_fallback")
    assert missing.scores.authority == 5.0 and missing.scores.persona_utility == 5.0
    assert second.url not in diagnostics.rejection_reasons
    assert (
        diagnostics.notes[second.url] == "evaluation_missing: deterministic score used"
    )


def test_composite_weights_freshness_more_for_recent_and_authority_more_for_evergreen() -> (
    None
):
    # Break caught: using one intent-insensitive formula for every freshness mode.
    fresh = candidate("fresh", "alpha.example")
    authoritative = candidate("authority", "beta.example")
    response = {
        "evaluations": [
            evaluation("fresh", freshness=10, authority=4, covered_angles=("cost",)),
            evaluation(
                "authority", freshness=4, authority=10, covered_angles=("cost",)
            ),
        ]
    }

    recent_results = run(
        agent_module.ResearchAgent(
            llm=FakeLLM(response), search=FakeSearch(), extractor=FakeExtractor()
        )._evaluate_pages(
            brief(FreshnessMode.RECENT),
            PersonaContext(),
            [validated(fresh), validated(authoritative)],
            RunAudit(),
        )
    )
    evergreen_results = run(
        agent_module.ResearchAgent(
            llm=FakeLLM(response), search=FakeSearch(), extractor=FakeExtractor()
        )._evaluate_pages(
            brief(FreshnessMode.EVERGREEN),
            PersonaContext(),
            [validated(fresh), validated(authoritative)],
            RunAudit(),
        )
    )

    assert recent_results[0].scores.composite > recent_results[1].scores.composite
    assert evergreen_results[1].scores.composite > evergreen_results[0].scores.composite


def test_evaluate_pages_applies_only_unusability_floors_and_ranks_the_rest() -> None:
    # Break caught: mid-quality pages being gated out instead of ranked, or off-topic garbage being accepted.
    pages = [
        candidate("off-topic", "a.example"),
        candidate("garbage", "b.example"),
        candidate("hollow", "c.example"),
        candidate("mediocre", "d.example"),
    ]
    llm = FakeLLM(
        {
            "evaluations": [
                evaluation(
                    "off-topic",
                    relevance=2.9,
                    freshness=10,
                    authority=10,
                    content_quality=10,
                ),
                evaluation(
                    "garbage",
                    relevance=10,
                    freshness=10,
                    authority=10,
                    content_quality=2.9,
                ),
                evaluation(
                    "hollow",
                    relevance=3,
                    freshness=0,
                    authority=0,
                    content_quality=3,
                    persona_utility=0,
                    covered_angles=(),
                ),
                evaluation(
                    "mediocre",
                    relevance=5.5,
                    freshness=5,
                    authority=5,
                    content_quality=5.5,
                ),
            ]
        }
    )
    research_agent = agent_module.ResearchAgent(
        llm=llm, search=FakeSearch(), extractor=FakeExtractor()
    )

    results = run(
        research_agent._evaluate_pages(
            brief(), PersonaContext(), [validated(page) for page in pages], RunAudit()
        )
    )

    assert [page.accepted for page in results] == [False, False, False, True]
    assert [page.rejection_reason for page in results] == [
        "relevance_below_floor",
        "content_quality_below_floor",
        "composite_below_floor",
        None,
    ]


def test_evaluate_pages_scores_undated_and_structurally_weak_pages_lower_instead_of_rejecting() -> (
    None
):
    # Break caught: the deterministic signals that used to gate pages having no effect on their rank.
    clean = candidate("clean", "alpha.example", published_at=NOW - timedelta(days=1))
    undated = candidate("undated", "beta.example", published_at=None)
    linky = candidate("linky", "gamma.example", published_at=NOW - timedelta(days=1))
    link_heavy = "\n".join(
        f"[Download evidence packet {number}](https://gamma.example/files/{number}/full-report.pdf) "
        "for the solar programme."
        for number in range(1, 80)
    )
    llm = FakeLLM(
        {
            "evaluations": [
                evaluation("clean"),
                evaluation("undated"),
                evaluation("linky"),
            ]
        }
    )
    research_agent = agent_module.ResearchAgent(
        config=replace(
            CONFIG, minimum_article_chars=100, maximum_link_to_visible_text_ratio=0.2
        ),
        llm=llm,
        search=FakeSearch(),
        extractor=FakeExtractor(),
        now=lambda: NOW,
    )
    prose = substantive_article("solar")
    pages = [
        validated(clean, document(clean, content=prose)),
        validated(undated, document(undated, content=prose)),
        validated(linky, document(linky, content=link_heavy)),
    ]

    results = run(
        research_agent._evaluate_pages(
            brief(FreshnessMode.RECENT), PersonaContext(), pages, RunAudit()
        )
    )
    by_id = {page.candidate.id: page for page in results}

    assert all(page.accepted for page in results)
    assert by_id["clean"].scores.freshness_known is True
    assert by_id["undated"].scores.freshness_known is False
    assert by_id["undated"].scores.freshness < by_id["clean"].scores.freshness
    assert by_id["undated"].scores.composite < by_id["clean"].scores.composite
    assert by_id["clean"].scores.structural_quality == 1.0
    assert by_id["linky"].scores.structural_quality < 1.0
    assert (
        by_id["linky"].scores.information_density
        < by_id["clean"].scores.information_density
    )


def test_evaluate_pages_uses_configured_acceptance_gates_and_weight_schedules() -> None:
    # Break caught: local scoring retaining hidden constants after scoring policy moved to Config.
    fresh = candidate("fresh", "alpha.example")
    authoritative = candidate("authoritative", "beta.example")
    config = replace(
        CONFIG,
        minimum_relevance_score=8.1,
        date_freshness_weight=0.0,
        time_sensitive_score_weights=(0, 1, 0, 0, 0, 0, 0),
        evergreen_score_weights=(0, 0, 1, 0, 0, 0, 0),
    )
    response = {
        "evaluations": [
            evaluation("fresh", relevance=8, freshness=10, authority=4),
            evaluation("authoritative", relevance=9, freshness=4, authority=10),
        ]
    }
    research_agent = agent_module.ResearchAgent(
        config=config,
        llm=FakeLLM(response),
        search=FakeSearch(),
        extractor=FakeExtractor(),
        now=lambda: NOW,
    )

    results = run(
        research_agent._evaluate_pages(
            brief(FreshnessMode.RECENT),
            PersonaContext(),
            [validated(fresh), validated(authoritative)],
            RunAudit(),
        )
    )

    assert results[0].rejection_reason == "relevance_below_floor"
    assert results[0].scores.composite == 10
    assert results[1].scores.composite == 4


def test_select_for_coverage_keeps_three_different_tavily_publishers() -> None:
    # Break caught: applying a provider cap to Tavily instead of a publisher-domain cap.
    pages = [
        scored_page("a", "alpha.example", 9.0, ("cost",)),
        scored_page("b", "beta.example", 8.5, ("policy",)),
        scored_page("c", "gamma.example", 8.0, ("adoption",)),
    ]

    selected = filters_module.select_for_coverage(
        pages, ("cost", "policy", "adoption"), 3, 4, 1
    )

    assert [page.candidate.id for page in selected] == ["a", "b", "c"]


def test_select_for_coverage_enforces_two_per_actual_publisher_domain() -> None:
    # Break caught: subdomains or search-provider labels bypassing the publisher cap.
    pages = [
        scored_page("a", "news.example.com", 9.0, ("cost",)),
        scored_page("b", "reviews.example.com", 8.8, ("policy",)),
        scored_page("c", "data.example.com", 8.6, ("adoption",)),
        scored_page("d", "other.example", 8.0, ("outcomes",)),
    ]

    selected = filters_module.select_for_coverage(
        pages, brief().required_angles, 3, 3, 2
    )

    assert len(selected) == 3
    assert (
        sum(page.candidate.url.endswith(("/a", "/b", "/c")) for page in selected) == 2
    )
    assert any(page.candidate.id == "d" for page in selected)


def test_select_for_coverage_prefers_marginal_uncovered_angle_after_strongest_page() -> (
    None
):
    # Break caught: sorting only by individual composite and ignoring joint coverage.
    pages = [
        scored_page("strongest", "alpha.example", 9.0, ("cost",)),
        scored_page("redundant", "beta.example", 8.8, ("cost",)),
        scored_page("coverage", "gamma.example", 8.0, ("policy",)),
    ]

    selected = filters_module.select_for_coverage(pages, ("cost", "policy"), 2, 2, 2)

    assert [page.candidate.id for page in selected] == ["strongest", "coverage"]


def test_select_for_coverage_always_starts_with_strongest_before_coverage_optimization() -> (
    None
):
    # Break caught: coverage bonus displacing the strongest accepted page in the first slot.
    pages = [
        scored_page("strongest", "alpha.example", 9.0, ("cost",)),
        scored_page("broad", "beta.example", 8.0, ("policy", "adoption", "outcomes")),
    ]

    selected = filters_module.select_for_coverage(
        pages, brief().required_angles, 1, 1, 2
    )

    assert [page.candidate.id for page in selected] == ["strongest"]


def test_select_for_coverage_starts_with_strongest_even_when_broader_page_has_bonus() -> (
    None
):
    # Break caught: applying coverage bonus to the first choice and displacing the strongest page.
    pages = [
        scored_page("strongest", "alpha.example", 9.0, ("cost",)),
        scored_page("broad", "beta.example", 8.6, ("policy", "adoption", "outcomes")),
    ]

    selected = filters_module.select_for_coverage(
        pages, brief().required_angles, 1, 1, 2
    )

    assert [page.candidate.id for page in selected] == ["strongest"]


def test_select_for_coverage_rejects_redundant_fourth_but_adds_missing_required_angle() -> (
    None
):
    # Break caught: always padding to four, or refusing a fourth page that closes a real gap.
    base = [
        scored_page("a", "alpha.example", 9.0, ("cost",)),
        scored_page("b", "beta.example", 8.8, ("policy",)),
        scored_page("c", "gamma.example", 8.6, ("adoption",)),
    ]
    redundant = scored_page("d", "delta.example", 8.4, ("cost",))
    useful = scored_page("d", "delta.example", 8.4, ("outcomes",))

    without_gain = filters_module.select_for_coverage(
        base + [redundant], brief().required_angles, 3, 4, 2
    )
    with_gain = filters_module.select_for_coverage(
        base + [useful], brief().required_angles, 3, 4, 2
    )

    assert [page.candidate.id for page in without_gain] == ["a", "b", "c"]
    assert [page.candidate.id for page in with_gain] == ["a", "b", "c", "d"]


def test_select_for_coverage_rejects_weak_arbitrary_fourth_perspective() -> None:
    # Break caught: a model-invented extra label bypassing credibility checks and padding the corpus to four.
    pages = [
        scored_page("a", "alpha.example", 9.0, ("cost",)),
        scored_page("b", "beta.example", 8.8, ("policy",)),
        scored_page("c", "gamma.example", 8.6, ("adoption",)),
        scored_page(
            "weak-extra",
            "delta.example",
            8.4,
            ("unverified extra perspective",),
            authority=4.0,
            content_quality=5.0,
        ),
    ]

    selected = filters_module.select_for_coverage(
        pages, ("cost", "policy", "adoption"), 3, 4, 2
    )

    assert [page.candidate.id for page in selected] == ["a", "b", "c"]


def test_select_for_coverage_accepts_credible_distinct_fourth_perspective() -> None:
    # Break caught: rejecting a strong independent angle merely because it is not a required angle.
    pages = [
        scored_page("a", "alpha.example", 9.0, ("cost",)),
        scored_page("b", "beta.example", 8.8, ("policy",)),
        scored_page("c", "gamma.example", 8.6, ("adoption",)),
        scored_page(
            "credible-extra",
            "delta.example",
            8.4,
            ("implementation perspective",),
            authority=8.0,
            content_quality=8.0,
        ),
    ]

    selected = filters_module.select_for_coverage(
        pages, ("cost", "policy", "adoption"), 3, 4, 2
    )

    assert [page.candidate.id for page in selected] == ["a", "b", "c", "credible-extra"]


def test_select_for_coverage_keeps_required_angle_fourth_even_when_its_quality_is_below_optional_floor() -> (
    None
):
    # Break caught: optional-fourth credibility gates blocking the last missing required research angle.
    pages = [
        scored_page("a", "alpha.example", 9.0, ("cost",)),
        scored_page("b", "beta.example", 8.8, ("policy",)),
        scored_page("c", "gamma.example", 8.6, ("adoption",)),
        scored_page(
            "required",
            "delta.example",
            6.1,
            ("outcomes",),
            authority=2.0,
            content_quality=2.0,
        ),
    ]

    selected = filters_module.select_for_coverage(
        pages, ("cost", "policy", "adoption", "outcomes"), 3, 4, 2
    )

    assert [page.candidate.id for page in selected] == ["a", "b", "c", "required"]


def test_select_for_coverage_keeps_materially_newer_fourth_even_when_its_quality_is_below_optional_floor() -> (
    None
):
    # Break caught: optional-perspective credibility gates blocking a materially newer evidentiary update.
    pages = [
        scored_page(
            "a", "alpha.example", 9.0, ("cost",), published_at=NOW - timedelta(days=20)
        ),
        scored_page(
            "b", "beta.example", 8.8, ("policy",), published_at=NOW - timedelta(days=18)
        ),
        scored_page(
            "c",
            "gamma.example",
            8.6,
            ("adoption",),
            published_at=NOW - timedelta(days=15),
        ),
        scored_page(
            "newer",
            "delta.example",
            6.1,
            ("cost",),
            published_at=NOW,
            authority=2.0,
            content_quality=2.0,
        ),
    ]

    selected = filters_module.select_for_coverage(
        pages, ("cost", "policy", "adoption"), 3, 4, 2
    )

    assert [page.candidate.id for page in selected] == ["a", "b", "c", "newer"]


def test_select_pages_delegates_to_configured_limits() -> None:
    # Break caught: the agent wrapper ignoring configured target, maximum, or publisher cap.
    pages = [
        scored_page("a", "alpha.example", 9.0, ("cost",)),
        scored_page("b", "alpha.example", 8.8, ("policy",)),
        scored_page("c", "beta.example", 8.6, ("adoption",)),
    ]
    research_agent = agent_module.ResearchAgent(
        config=replace(CONFIG, target_pages=2, max_pages=2, max_per_publisher_domain=1),
        llm=FakeLLM(),
        search=FakeSearch(),
        extractor=FakeExtractor(),
    )

    selected = research_agent._select_pages(pages, brief())

    assert len(selected) == 2
    assert (
        len({filters_module.publisher_domain(page.candidate.url) for page in selected})
        == 2
    )


def test_composite_is_capped_relative_to_relevance_so_authority_cannot_carry_an_off_topic_page() -> (
    None
):
    # Break caught: a fresh, authoritative news page about the wrong subject outranking an on-topic page
    # (seen when a Business Insider piece about AI jokes beat pages of actual joke material).
    off_topic = candidate("off-topic", "news.example", published_at=NOW)
    on_topic = candidate("on-topic", "blog.example", published_at=None)
    llm = FakeLLM(
        {
            "evaluations": [
                evaluation(
                    "off-topic",
                    relevance=4,
                    freshness=10,
                    authority=10,
                    content_quality=9,
                    persona_utility=8,
                    covered_angles=("cost",),
                ),
                evaluation(
                    "on-topic",
                    relevance=9,
                    freshness=6,
                    authority=4,
                    content_quality=6,
                    persona_utility=8,
                    covered_angles=("cost", "policy"),
                ),
            ]
        }
    )
    research_agent = agent_module.ResearchAgent(
        llm=llm, search=FakeSearch(), extractor=FakeExtractor(), now=lambda: NOW
    )

    results = run(
        research_agent._evaluate_pages(
            brief(),
            PersonaContext(),
            [validated(off_topic), validated(on_topic)],
            RunAudit(),
        )
    )
    by_id = {page.candidate.id: page for page in results}

    assert by_id["off-topic"].scores.composite <= 4 + CONFIG.relevance_cap_margin
    assert by_id["on-topic"].scores.composite > by_id["off-topic"].scores.composite


def test_media_urls_come_from_the_raw_document_because_cleaning_strips_image_links() -> (
    None
):
    # Break caught: the composer's media list always empty because URLs were read after cleaning removed them.
    page = candidate("illustrated", "alpha.example")
    raw = (
        substantive_article("solar")
        + "\n\n![Image 1: A rooftop array](https://img.example.com/array.jpg)\n"
    )
    llm = FakeLLM({"evaluations": [evaluation("illustrated")]})
    research_agent = agent_module.ResearchAgent(
        config=replace(CONFIG, minimum_article_chars=100),
        llm=llm,
        search=FakeSearch(),
        extractor=FakeExtractor(),
        now=lambda: NOW,
    )
    doc = document(page, content=raw)
    cleaned = filters_module.clean_article_content(raw)
    assert "https://img.example.com/array.jpg" not in cleaned

    results = run(
        research_agent._evaluate_pages(
            brief(), PersonaContext(), [(page, doc, cleaned, cleaned[:180])], RunAudit()
        )
    )

    assert results[0].media == ["https://img.example.com/array.jpg"]
