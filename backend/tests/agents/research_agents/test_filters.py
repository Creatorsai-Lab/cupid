from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.agents.research_agents.config import CONFIG
from app.agents.research_agents.filters import (
    FRESH,
    STALE,
    UNKNOWN_FRESHNESS,
    _date_freshness_score,
    _published_at_from_url,
    article_rejection_reason,
    build_ranking_view,
    canonicalize_url,
    clean_article_content,
    early_rejection_reason,
    freshness_component,
    freshness_status,
    is_fresh_enough,
    publisher_domain,
    structural_quality,
)
from app.agents.research_agents.models import (
    CandidatePage,
    ExtractedDocument,
    FreshnessMode,
    ResearchBrief,
)


def make_brief(
    mode: FreshnessMode = FreshnessMode.EVERGREEN,
    window: int | None = None,
) -> ResearchBrief:
    return ResearchBrief(
        topic="solar energy",
        main_keywords=("India", "Solar"),
        user_goal="Create a factual explainer",
        required_angles=("policy", "cost"),
        freshness_mode=mode,
        freshness_window_days=window,
    )


def make_candidate(published_at: datetime | None) -> CandidatePage:
    return CandidatePage(
        id="page-1",
        url="https://news.example.com/article",
        canonical_url="https://news.example.com/article",
        publisher_domain="example.com",
        search_provider="test",
        title="Solar policy update",
        published_at=published_at,
        search_rank=1,
    )


def make_document(content: str) -> ExtractedDocument:
    return ExtractedDocument(
        candidate_id="page-1",
        content=content,
        extraction_provider="test",
    )


def test_canonicalize_url_removes_tracking_sorts_query_and_preserves_content_parameters() -> (
    None
):
    # Break caught: treating tracking keys as article identity or losing a content-defining query.
    assert (
        canonicalize_url(
            "HTTPS://News.Example.com:443//reports/solar/?b=2&utm_source=feed&article=42&a=1#section"
        )
        == "https://news.example.com/reports/solar?a=1&article=42&b=2"
    )


def test_canonicalize_url_treats_www_as_the_same_identity() -> None:
    # Break caught: deduplicating a publisher's www and apex article URLs separately.
    assert canonicalize_url(
        "https://www.example.com/article?b=2&a=1"
    ) == canonicalize_url("https://example.com/article?a=1&b=2")


def test_canonicalize_url_preserves_brackets_around_a_public_ipv6_host() -> None:
    # Break caught: emitting an ambiguous, unparsable canonical URL for a valid IPv6 host.
    assert canonicalize_url("https://[2606:4700:4700::1111]/article?b=2&a=1") == (
        "https://[2606:4700:4700::1111]/article?a=1&b=2"
    )


def test_publisher_domain_uses_registrable_domain_for_multi_part_suffix() -> None:
    # Break caught: using only the final two hostname labels.
    assert (
        publisher_domain("https://news.department.example.co.uk/story")
        == "example.co.uk"
    )


@pytest.mark.parametrize(
    "url",
    (
        "ftp://example.com/file",
        "https://localhost/article",
        "https://127.0.0.1/article",
        "https://10.0.0.4/article",
        "https://[::1]/article",
        "https://user:password@example.com/article",
    ),
)
def test_early_rejection_rejects_non_http_and_unsafe_targets(url: str) -> None:
    # Break caught: allowing an extractor to fetch an unsafe target.
    assert early_rejection_reason(url, "A substantive title", CONFIG) == "unsafe_url"


@pytest.mark.parametrize(
    "url",
    (
        "https://exa mple.com/article",
        "https://example..com/article",
        "https://-invalid.example/article",
        "https://invalid-.example/article",
        "https://example.com:65536/article",
        "https://example.com:notaport/article",
    ),
)
def test_early_rejection_rejects_malformed_hosts_and_ports_without_canonicalization_errors(
    url: str,
) -> None:
    # Break caught: accepting malformed network targets or raising while normalizing one.
    assert early_rejection_reason(url, "A substantive title", CONFIG) == "unsafe_url"
    assert isinstance(canonicalize_url(url), str)


def test_early_rejection_rejects_saved_category_page_regression() -> None:
    # Break caught: extracting a category landing page as an article.
    url = "https://manjulaskitchen.com/category/holidays-festivals/krishna-janmashtami"
    assert (
        early_rejection_reason(url, "Krishna Janmashtami Recipes", CONFIG)
        == "listing_url"
    )


@pytest.mark.parametrize(
    "url,title",
    (
        ("https://example.com/tag/solar", "Solar tag"),
        ("https://example.com/2026/09/", "September archive"),
        ("https://example.com/feed", "Feed"),
        ("https://example.com/search?q=solar", "Search results"),
        ("https://example.com/page/2", "Page 2"),
        ("https://example.com/", "Example Home"),
        ("https://example.com/latest", "Latest stories"),
    ),
)
def test_early_rejection_identifies_common_listing_pages(url: str, title: str) -> None:
    # Break caught: extracting navigational or aggregate pages.
    assert early_rejection_reason(url, title, CONFIG) == "listing_url"


@pytest.mark.parametrize(
    "url",
    (
        "https://example.com/2026/09/",
        "https://example.com/rss",
        "https://example.com/feed",
        "https://example.com/atom",
        "https://example.com/atom.xml",
        "https://example.com/results?q=solar",
        "https://example.com/search/solar",
    ),
)
def test_early_rejection_identifies_url_driven_archives_feeds_and_searches(
    url: str,
) -> None:
    # Break caught: relying on aggregate-page title wording instead of its URL structure.
    assert early_rejection_reason(url, "A substantive title", CONFIG) == "listing_url"


def test_early_rejection_keeps_date_prefixed_article_url() -> None:
    # Break caught: rejecting ordinary dated article permalinks as archives.
    assert (
        early_rejection_reason(
            "https://example.com/2026/09/solar-policy-update",
            "Solar policy update",
            CONFIG,
        )
        is None
    )


def test_freshness_rejects_undated_time_sensitive_candidate_but_allows_evergreen() -> (
    None
):
    # Break caught: accepting unknown-age news or rejecting useful evergreen material.
    now = datetime(2026, 9, 4, tzinfo=UTC)
    candidate = make_candidate(None)
    assert not is_fresh_enough(candidate, make_brief(FreshnessMode.RECENT, 30), now)
    assert is_fresh_enough(candidate, make_brief(), now)


def test_freshness_status_distinguishes_unknown_from_stale() -> None:
    # Break caught: treating "no date found" as proof of staleness and discarding fetchable evidence.
    now = datetime(2026, 9, 4, tzinfo=UTC)
    brief = make_brief(FreshnessMode.RECENT, 30)
    assert freshness_status(make_candidate(None), brief, now) == UNKNOWN_FRESHNESS
    assert (
        freshness_status(make_candidate(now - timedelta(days=31)), brief, now) == STALE
    )
    assert (
        freshness_status(make_candidate(now - timedelta(days=3)), brief, now) == FRESH
    )
    assert freshness_status(make_candidate(None), make_brief(), now) == FRESH


def test_freshness_component_penalises_unknown_dates_and_blends_known_dates() -> None:
    # Break caught: an undated page scoring identically to a dated one, or the date being ignored.
    now = datetime(2026, 9, 4, tzinfo=UTC)
    brief = make_brief(FreshnessMode.RECENT, 30)
    undated_score, undated_known = freshness_component(
        9.0, make_candidate(None), brief, now, CONFIG
    )
    dated_score, dated_known = freshness_component(
        9.0, make_candidate(now - timedelta(days=1)), brief, now, CONFIG
    )
    edge_score, _ = freshness_component(
        9.0, make_candidate(now - timedelta(days=30)), brief, now, CONFIG
    )

    assert undated_known is False and dated_known is True
    assert undated_score == pytest.approx(9.0 * CONFIG.undated_freshness_multiplier)
    assert dated_score == pytest.approx(0.6 * 10.0 + 0.4 * 9.0)
    assert edge_score < dated_score
    assert _date_freshness_score(now - timedelta(days=30), now, 30) == pytest.approx(
        5.0
    )
    assert _date_freshness_score(now - timedelta(days=60), now, 30) == pytest.approx(
        0.0
    )
    evergreen_score, _ = freshness_component(
        6.0, make_candidate(None), make_brief(), now, CONFIG
    )
    assert evergreen_score == 6.0


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://news.example.com/2026/09/03/solar-policy",
            datetime(2026, 9, 3, tzinfo=UTC),
        ),
        (
            "https://aninews.in/news/world/asia/confident-under-indias-chairship-brics-2026-summit20260609224018",
            datetime(2026, 6, 9, tzinfo=UTC),
        ),
        ("https://example.com/story-20260931", None),
        ("https://example.com/2026/09/solar-policy", None),
        ("https://example.com/report-1234567890123", None),
    ],
)
def test_published_at_from_url_accepts_full_dates_including_compact_cms_timestamps(
    url: str, expected
) -> None:
    # Break caught: dropping a clearly dated news URL as undated because the CMS glued the date to the slug.
    assert _published_at_from_url(url) == expected


def test_freshness_applies_inclusive_configured_window() -> None:
    # Break caught: accepting stale pages or rejecting a page precisely at the cutoff.
    now = datetime(2026, 9, 4, tzinfo=UTC)
    brief = make_brief(FreshnessMode.RECENT, 30)
    assert is_fresh_enough(make_candidate(now - timedelta(days=30)), brief, now)
    assert not is_fresh_enough(make_candidate(now - timedelta(days=31)), brief, now)


def test_freshness_rejects_time_sensitive_dates_more_than_a_day_in_the_future() -> None:
    # Break caught: treating a clearly erroneous future publication date as current evidence.
    now = datetime(2026, 9, 4, tzinfo=UTC)
    brief = make_brief(FreshnessMode.RECENT, 30)
    assert is_fresh_enough(make_candidate(now + timedelta(hours=24)), brief, now)
    assert not is_fresh_enough(
        make_candidate(now + timedelta(hours=24, seconds=1)), brief, now
    )


def test_clean_article_content_preserves_unicode_and_strips_jina_headers() -> None:
    # Break caught: corrupting normal Unicode or leaking reader metadata into the article.
    raw = """Title: Solar Update
URL Source: https://example.com/solar
Published Time: 2026-09-04
Markdown Content:

# Let’s test — café

Useful article text.
"""
    assert clean_article_content(raw) == "# Let’s test — café\n\nUseful article text."


def test_clean_article_content_keeps_markdown_link_labels_and_removes_bare_urls() -> (
    None
):
    # Break caught: deleting linked article wording or retaining URL noise.
    assert (
        clean_article_content(
            "Read [the official report](https://example.com/report). More at https://example.com/more."
        )
        == "Read the official report. More at"
    )


def test_clean_article_content_preserves_nested_list_indentation() -> None:
    # Break caught: flattening nested Markdown lists while normalizing their inline whitespace.
    assert clean_article_content(
        "- Parent   item\n  - Child   item\n    - Grandchild"
    ) == ("- Parent item\n  - Child item\n    - Grandchild")
    assert (
        clean_article_content("- Parent\n\t- Tab-indented child")
        == "- Parent\n\t- Tab-indented child"
    )


def test_clean_article_content_removes_only_standalone_navigation_and_footer_rows() -> (
    None
):
    # Break caught: final corpus retaining unmistakable standalone navigation or legal-footer boilerplate.
    raw = """[Home](https://example.com/) | [News](https://example.com/news) | [Contact](https://example.com/contact)

# Solar policy briefing

The article explains the evidence, implementation limits, and local outcomes in complete prose.

© 2026 Example Research Institute. All rights reserved.
"""

    assert clean_article_content(raw) == (
        "# Solar policy briefing\n\n"
        "The article explains the evidence, implementation limits, and local outcomes in complete prose."
    )


def test_navigation_contamination_preserves_prose_that_mentions_privacy_and_copyright() -> (
    None
):
    # Break caught: matching a legal-term substring in article prose as footer contamination.
    raw = """# Editorial standards

The privacy policy explains how interview consent is documented, while copyright analysis identifies the licence for each chart.

## Evidence handling

Editors compare publication records, interview transcripts, and source files before describing a programme's results.

## Reader guidance

The report distinguishes legal context from a footer notice and links every conclusion to its supporting evidence.
"""
    cleaned = clean_article_content(raw)
    config = replace(
        CONFIG, minimum_article_chars=100, maximum_navigation_footer_ratio=0.0
    )

    assert cleaned == raw.strip()
    assert article_rejection_reason(make_document(raw), cleaned, config) is None


def test_article_rejection_enforces_minimum_and_maximum_without_truncation() -> None:
    # Break caught: accepting unusably short material or silently truncating oversized pages.
    config = replace(CONFIG, minimum_article_chars=20, max_clean_content_chars=40)
    assert (
        article_rejection_reason(make_document("short"), "short", config) == "too_short"
    )
    oversized = "x" * 41
    assert (
        article_rejection_reason(make_document(oversized), oversized, config)
        == "too_long"
    )


def test_structural_quality_penalises_repeated_listing_cards_without_rejecting() -> (
    None
):
    # Break caught: a long aggregate page ranking as high as a real article, or being discarded outright.
    cards = "\n\n".join(
        f"## Story {number}\nA short teaser for this story. [Read more](https://example.com/{number})"
        for number in range(1, 30)
    )
    cleaned = clean_article_content(cards)
    config = replace(CONFIG, minimum_article_chars=100, max_clean_content_chars=10_000)
    assert article_rejection_reason(make_document(cards), cleaned, config) is None
    multiplier, flags = structural_quality(make_document(cards), cleaned, config)
    assert "listing_body" in flags
    assert multiplier <= config.listing_body_penalty


def test_article_rejection_keeps_structured_multiheading_article_with_citations_and_tables() -> (
    None
):
    # Break caught: heading, link, and short-block counts alone classifying a real structured article as a listing.
    sections = "\n\n".join(
        f"## Evidence question {number}\n\n"
        f"The analysis explains distinct policy finding {number}, its method, and the local implementation context. "
        f"See [primary source {number}](https://example.com/evidence/{number}) and "
        f"[audit record {number}](https://example.com/audit/{number}) for the underlying evidence.\n\n"
        f"| Measure | Finding |\n| --- | --- |\n| Indicator {number} | Independently verified outcome {number}. |"
        for number in range(1, 11)
    )
    raw = f"# Community solar evidence\n\n{sections}"
    cleaned = clean_article_content(raw)
    config = replace(CONFIG, minimum_article_chars=100, max_clean_content_chars=10_000)

    assert article_rejection_reason(make_document(raw), cleaned, config) is None
    assert structural_quality(make_document(raw), cleaned, config) == (1.0, ())


def test_structural_quality_penalises_long_low_information_repetition() -> None:
    # Break caught: a body made from one repeated sentence ranking level with substantive prose.
    repeated = (
        "The report repeats the same generic statement without adding evidence. " * 120
    ).strip()
    config = replace(
        CONFIG, minimum_article_chars=100, minimum_structural_information_density=4.0
    )

    assert article_rejection_reason(make_document(repeated), repeated, config) is None
    multiplier, flags = structural_quality(make_document(repeated), repeated, config)
    assert flags == ("low_information_density",)
    assert config.structural_penalty_floor <= multiplier < 1.0


def test_structural_quality_penalises_link_dominated_pseudo_article() -> None:
    # Break caught: many linked destinations can inflate a pseudo-article beyond the minimum text length.
    pseudo_article = "\n".join(
        f"[Download evidence packet {number}](https://example.com/files/{number}/full-report.pdf) "
        "for the solar programme."
        for number in range(1, 80)
    )
    cleaned = clean_article_content(pseudo_article)
    config = replace(
        CONFIG,
        minimum_article_chars=100,
        maximum_link_to_visible_text_ratio=0.20,
    )

    assert (
        article_rejection_reason(make_document(pseudo_article), cleaned, config) is None
    )
    multiplier, flags = structural_quality(
        make_document(pseudo_article), cleaned, config
    )
    assert "link_dominated" in flags
    assert multiplier < 1.0
    lenient = replace(config, maximum_link_to_visible_text_ratio=1.0)
    assert (
        structural_quality(make_document(pseudo_article), cleaned, lenient)[0]
        > multiplier
    )


def test_structural_quality_penalises_navigation_and_footer_heavy_page() -> None:
    # Break caught: a page whose body is dominated by unmistakable navigation and footer rows reaches evaluation.
    navigation = "\n".join(
        "[Home](https://example.com/) | [News](https://example.com/news) | "
        "[Topics](https://example.com/topics) | [Contact](https://example.com/contact) | "
        "[Privacy](https://example.com/privacy)"
        for _ in range(35)
    )
    article = "\n\n".join(
        (
            "# Solar policy evidence\n\n"
            "A short factual introduction describes the programme and its publication method.",
            "## Evidence\n\n"
            "The limited article text remains intact, but it cannot outweigh the surrounding navigation.",
        )
    )
    raw = f"{navigation}\n\n{article}\n\n© 2026 Example. All rights reserved."
    cleaned = clean_article_content(raw)
    config = replace(
        CONFIG,
        minimum_article_chars=100,
        maximum_navigation_footer_ratio=0.50,
    )

    assert len(cleaned) >= config.minimum_article_chars
    assert article_rejection_reason(make_document(raw), cleaned, config) is None
    multiplier, flags = structural_quality(make_document(raw), cleaned, config)
    assert "navigation_or_footer_heavy" in flags
    assert multiplier < 1.0


def test_structural_validation_keeps_substantive_article_with_normal_citations_and_navigation_fragments() -> (
    None
):
    # Break caught: structural heuristics discarding ordinary article prose because it has citations or a small nav row.
    raw = """[Home](https://example.com/) | [News](https://example.com/news) | [Contact](https://example.com/contact)

# Solar policy — café briefing

The programme combines auction data, grid planning, and consumer safeguards. Analysts compared quarterly filings,
interviews, and official datasets to explain where the policy works and where implementation still varies.

## Evidence table

| Metric | Finding |
| --- | --- |
| Cost | Installation costs declined in the latest reporting period. |
| Access | Rural cooperative participation rose after the new guidance. |

## What changed

1. Agencies published clearer eligibility guidance.
2. Cooperatives reported project-level delivery details.
3. Regulators retained independent review requirements.

The full article distinguishes preliminary observations from confirmed findings and links its three primary citations:
[energy ministry report](https://example.com/primary/ministry),
[grid operator data](https://example.com/primary/grid), and
[audit methodology](https://example.com/primary/audit).

Further paragraphs explain costs, policy design, adoption barriers, and outcomes with concrete context for each claim.
"""
    cleaned = clean_article_content(raw)
    config = replace(CONFIG, minimum_article_chars=300)

    assert "# Solar policy — café briefing" in cleaned
    assert "| Metric | Finding |" in cleaned
    assert "1. Agencies published clearer eligibility guidance." in cleaned
    assert article_rejection_reason(make_document(raw), cleaned, config) is None


def test_build_ranking_view_keeps_intro_and_relevant_sections_within_limit() -> None:
    # Break caught: spending the ranking budget on irrelevant text instead of brief-relevant evidence.
    content = """# Solar overview

This introduction explains the national solar transition.

## Celebrity gossip

This unrelated section is deliberately long but irrelevant.

## India policy changes

India announced a solar policy with clear targets.

## Cost analysis

Solar cost data shows declining installation prices.
"""
    view = build_ranking_view(content, make_brief(), limit=220)
    assert "This introduction explains" in view
    assert "India policy changes" in view
    assert "Solar cost data" in view
    assert "Celebrity gossip" not in view
    assert len(view) <= 220


def test_build_ranking_view_does_not_mutate_or_truncate_cleaned_article_content() -> (
    None
):
    # Break caught: deriving the evaluator view by modifying the deliverable article body.
    content = "# Heading\n\n" + ("Complete article sentence. " * 100)
    original = content[:]
    view = build_ranking_view(content, make_brief(), limit=120)
    assert len(view) <= 120
    assert content == original
    assert len(content) > len(view)


def test_clean_article_content_strips_site_furniture_menus_cards_and_fundraising_but_keeps_prose() -> (
    None
):
    # Break caught: the composer receiving navigation menus, story cards, image placeholders, glued
    # bylines and subscription appeals alongside the article (seen on a real Guardian page).
    raw = """Skip to main contentSkip to navigation

## Support the Guardian

Fund independent journalism, and save money

[Claim discount](https://support.example.com)

* [News](https://example.com/news)
* [Opinion](https://example.com/opinion)
* - [x] [Sport](https://example.com/sport)
    * [Soccer](https://example.com/soccer)

![Image 4: Fang performing, with repeated images behind.](https://i.example.com/4.jpg)

# For women frustrated by sexism, female comics are offering a release

Standup comedy gives women a space to talk about sensitive topics.

ByAmy Hawkins

Packed into a small theatre in east Beijing, more than 100 people are giddy with anticipation. "Who did you come to see?" asks the MC.

## Navigating the minefield of political topics

Fang is one of several female comics to have emerged in recent years, joking about everyday sexism.

[]()

## At this dangerous time

We hope you appreciated this article. Can we ask you to support the Guardian at this critical time for journalism? Our most impactful monthly support option is just $7.50 a month.

According to a leading watchdog, democracy is now more imperiled than at any point since the 1960s.

If you can, please support us today. All gifts are gratefully received, and you will see far fewer fundraising messages like this.

Support once from just $1

* Far fewer asks for support
* Ad-free reading on all your devices

Explore more on these topics

* [China](https://example.com/china)
* [Comedy](https://example.com/comedy)

## Most viewed

* [![Image 10 #### The west is in freefall](https://i.example.com/10.jpg)](https://example.com/freefall)
* [![Image 11 #### Why did every fish perish](https://i.example.com/11.jpg)](https://example.com/fish)

## Women in China

* [![Image 15 ### They were forced into marriage 17 Jun 2026]()](https://example.com/marriage)

Share

Reuse this content

© 2026 Guardian News & Media Limited. All rights reserved.
"""
    cleaned = clean_article_content(raw)

    assert cleaned.startswith("# For women frustrated by sexism")
    assert "Packed into a small theatre" in cleaned
    assert "## Navigating the minefield of political topics" in cleaned
    assert "joking about everyday sexism" in cleaned
    for noise in (
        "Skip to main",
        "Support the Guardian",
        "Claim discount",
        "Opinion",
        "Soccer",
        "Image 4",
        "ByAmy",
        "At this dangerous time",
        "$7.50",
        "gratefully received",
        "Support once",
        "Ad-free",
        "Explore more",
        "Most viewed",
        "freefall",
        "Women in China",
        "forced into marriage",
        "Share",
        "Reuse this content",
        "All rights reserved",
        "[]()",
    ):
        assert noise not in cleaned, noise
    assert "\n\n\n" not in cleaned


def test_clean_article_content_keeps_short_plain_lists_and_inline_links_in_real_articles() -> (
    None
):
    # Break caught: the furniture rules eating a legitimate short list or a heading glued to its paragraph.
    raw = """# BRICS members

BRICS originally stood for five countries. See [the charter](https://example.com/charter) for details.

* B – Brazil
* R – Russia
* I – India

## Story 1
A short teaser for this story. [Read more](https://example.com/1)
"""
    cleaned = clean_article_content(raw)

    assert "* B – Brazil\n* R – Russia\n* I – India" in cleaned
    assert "See the charter for details." in cleaned
    assert "## Story 1\n\nA short teaser for this story. Read more" in cleaned
