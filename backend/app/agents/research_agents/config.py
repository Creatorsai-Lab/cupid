import os
from dataclasses import dataclass, field
from math import isfinite

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Immutable provider settings and hard limits for the research pipeline."""

    groq_api_key: str = field(
        default_factory=lambda: os.getenv("GROQ_API_KEY", ""), repr=False
    )
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"
    groq_fast_model: str = "openai/gpt-oss-20b"
    nvidia_api_key: str = field(
        default_factory=lambda: os.getenv("NVIDIA_API_KEY", ""), repr=False
    )
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    # deepseek-v4-pro was retired (HTTP 410); v4.1-flash is the live successor on NVIDIA NIM.
    nvidia_model: str = "deepseek-ai/deepseek-v4.1-flash"
    # Per-stage provider chains, tried in order. Names: "groq" (groq_model),
    # "groq_fast" (groq_fast_model), "nvidia" (nvidia_model). Groq meters tokens per
    # model, so every stage uses the one 120b model: the 20b quota stays untouched for
    # other agents, and a failed or rate-limited stage uses its deterministic fallback
    # instead of spending a second model. Listing more names opts a stage into failover;
    # NVIDIA's free endpoint measured 50-120s per call, beyond every stage timeout.
    planning_provider_chain: tuple[str, ...] = ("groq",)
    evaluation_provider_chain: tuple[str, ...] = ("groq",)
    default_provider_chain: tuple[str, ...] = ("groq",)
    # Groq's gpt-oss models spend hidden reasoning tokens that count against the quota
    # (measured: 650-1,250 per evaluation at the default effort, 17 at "low"). Planning
    # benefits from some deliberation; scoring pages against a rubric does not.
    planning_reasoning_effort: str = "medium"
    evaluation_reasoning_effort: str = "low"
    tavily_api_key: str = field(
        default_factory=lambda: os.getenv("TAVILY_API_KEY", ""), repr=False
    )
    searxng_url: str = field(default_factory=lambda: os.getenv("SEARXNG_URL", ""))
    jina_reader_base_url: str = "https://r.jina.ai/http://"
    blocked_domains: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "facebook.com",
                "fb.com",
                "fb.me",
                "instagram.com",
                "instagr.am",
                "twitter.com",
                "x.com",
                "t.co",
                "tiktok.com",
                "tiktokv.com",
                "youtube.com",
                "youtu.be",
                "ytimg.com",
                "pinterest.com",
                "pin.it",
                "snapchat.com",
                "snap.com",
                "threads.net",
            }
        )
    )
    target_pages: int = 3
    max_pages: int = 4
    # Fetch generously: ~1/3 of fetches fail (paywall, download, timeout), so the shortlist
    # must over-fetch relative to target_pages or the final corpus starves.
    shortlist_size: int = 10
    max_shortlist_size: int = 12
    search_results_per_query: int = 3
    max_queries: int = 6
    min_queries: int = 3
    max_gap_searches: int = 1
    hard_timeout_seconds: float = 45.0
    planning_timeout_seconds: float = 10.0
    search_timeout_seconds: float = 10.0
    extraction_timeout_seconds: float = 18.0
    page_extraction_timeout_seconds: float = 15.0
    # One structured call scores the whole shortlist; ~1.3s per page on the current model.
    evaluation_timeout_seconds: float = 15.0
    evaluation_reserve_seconds: float = 8.0
    gap_min_remaining_seconds: float = 12.0
    search_concurrency: int = 5
    extract_concurrency: int = 10
    max_download_bytes: int = 5_000_000
    max_clean_content_chars: int = 120_000
    # Per-page evaluator view cap: about what each of a typical 7-page shortlist gets from the
    # budget below, so a small recovery batch is judged on the same amount of text instead of
    # spending extra tokens on longer views.
    ranking_view_chars: int = 2_400
    # Total characters of page views in one evaluator call. Groq's on-demand tier allows
    # 8,000 tokens per minute shared with the planning call; ~16k chars keeps the batch
    # under that even with a full shortlist (per-page view = budget / pages, capped above).
    evaluation_view_char_budget: int = 16_000
    evaluation_view_min_chars: int = 600
    minimum_article_chars: int = 400
    cache_ttl_seconds: int = 21_600
    max_per_publisher_domain: int = 2
    cache_maxsize: int = 1_000
    llm_concurrency: int = 3
    # Score floors below mark a page as unusable (off-topic or garbage), not "not great".
    # Ranking by composite decides quality; these floors only remove pages the composer
    # could never use.
    # Planner validation tolerance for plain words. A request anchor is a term the user typed
    # that the brief must keep; named terms (a place, an acronym, a year, an amount) are never
    # optional. With self-introductions, examples and content forms ignored, real briefs for
    # the saved requests lose at most one plain word, so 1 keeps them while a brief that drops
    # a two-word subject ("career hacks") falls back. Tests pin 0 to prove the mechanism.
    max_missing_brief_anchors: int = 1
    # Gap queries are cheap to reject: the deterministic fallback query always carries
    # every declared entity and constraint, so strict validation costs nothing.
    max_missing_gap_declarations: int = 0
    minimum_relevance_score: float = 3.0
    minimum_content_quality_score: float = 3.0
    minimum_composite_score: float = 3.0
    # Structural signals below are soft: crossing them multiplies the page's
    # information_density component by a penalty instead of rejecting the page.
    minimum_structural_information_density: float = 3.60
    structural_penalty_floor: float = 0.25
    listing_body_penalty: float = 0.5
    # Freshness is a score, not a gate. Undated pages keep the evaluator's content-based
    # freshness judgement scaled by this multiplier; dated pages blend the date-derived
    # score with the evaluator's score using date_freshness_weight.
    undated_freshness_multiplier: float = 0.7
    date_freshness_weight: float = 0.6
    maximum_link_to_visible_text_ratio: float = 0.35
    maximum_navigation_footer_ratio: float = 0.50
    minimum_distinct_fourth_authority_score: float = 7.0
    minimum_distinct_fourth_content_quality_score: float = 7.0
    minimum_distinct_fourth_composite_score: float = 7.0
    # Component order: relevance, freshness, authority, information_density, persona_utility,
    # novelty, content_quality. Relevance carries the largest weight in both schedules: an
    # authoritative page about the wrong thing is worthless to the composer.
    evergreen_score_weights: tuple[float, ...] = (
        0.30,
        0.05,
        0.20,
        0.15,
        0.08,
        0.05,
        0.17,
    )
    time_sensitive_score_weights: tuple[float, ...] = (
        0.28,
        0.28,
        0.08,
        0.10,
        0.06,
        0.05,
        0.15,
    )
    # No page may rank more than this many points above its own relevance score, so
    # authority and freshness can never carry an off-topic page past an on-topic one.
    relevance_cap_margin: float = 2.0

    def __post_init__(self) -> None:
        for field_name in (
            "hard_timeout_seconds",
            "planning_timeout_seconds",
            "search_timeout_seconds",
            "extraction_timeout_seconds",
            "page_extraction_timeout_seconds",
            "evaluation_timeout_seconds",
            "evaluation_reserve_seconds",
            "gap_min_remaining_seconds",
        ):
            value = getattr(self, field_name)
            if (
                not isinstance(value, (int, float))
                or not isfinite(value)
                or value <= 0.0
            ):
                raise ValueError(f"{field_name} must be a positive finite duration")

        if self.gap_min_remaining_seconds < self.evaluation_reserve_seconds:
            raise ValueError(
                "gap_min_remaining_seconds must be at least evaluation_reserve_seconds"
            )

        if self.page_extraction_timeout_seconds >= self.extraction_timeout_seconds:
            raise ValueError(
                "page_extraction_timeout_seconds must be below extraction_timeout_seconds"
            )

        for field_name in (
            "relevance_cap_margin",
            "minimum_relevance_score",
            "minimum_content_quality_score",
            "minimum_composite_score",
            "minimum_structural_information_density",
            "minimum_distinct_fourth_authority_score",
            "minimum_distinct_fourth_content_quality_score",
            "minimum_distinct_fourth_composite_score",
        ):
            value = getattr(self, field_name)
            if (
                not isinstance(value, (int, float))
                or not isfinite(value)
                or not 0.0 <= value <= 10.0
            ):
                raise ValueError(f"{field_name} must be a finite score from 0 to 10")

        if not isinstance(self.max_shortlist_size, int) or self.max_shortlist_size < 1:
            raise ValueError("max_shortlist_size must be a positive integer")
        for field_name in (
            "planning_provider_chain",
            "evaluation_provider_chain",
            "default_provider_chain",
        ):
            chain = tuple(getattr(self, field_name))
            if not chain or any(
                name not in {"groq", "groq_fast", "nvidia"} for name in chain
            ):
                raise ValueError(
                    f'{field_name} must list one or more of "groq", "groq_fast", "nvidia"'
                )
            if len(set(chain)) != len(chain):
                raise ValueError(f"{field_name} must not repeat a provider")
            object.__setattr__(self, field_name, chain)

        for field_name in ("max_missing_brief_anchors", "max_missing_gap_declarations"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")

        for field_name in ("planning_reasoning_effort", "evaluation_reasoning_effort"):
            if getattr(self, field_name) not in {"low", "medium", "high"}:
                raise ValueError(f'{field_name} must be "low", "medium", or "high"')

        for field_name in ("evaluation_view_char_budget", "evaluation_view_min_chars"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer")

        for field_name in (
            "maximum_link_to_visible_text_ratio",
            "maximum_navigation_footer_ratio",
            "structural_penalty_floor",
            "listing_body_penalty",
            "undated_freshness_multiplier",
            "date_freshness_weight",
        ):
            value = getattr(self, field_name)
            if (
                not isinstance(value, (int, float))
                or not isfinite(value)
                or not 0.0 <= value <= 1.0
            ):
                raise ValueError(f"{field_name} must be a finite ratio from 0 to 1")

        for field_name in ("evergreen_score_weights", "time_sensitive_score_weights"):
            try:
                weights = tuple(float(weight) for weight in getattr(self, field_name))
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"{field_name} must contain numeric weights"
                ) from error
            if len(weights) != 7:
                raise ValueError(f"{field_name} must contain exactly seven weights")
            if any(not isfinite(weight) or weight < 0.0 for weight in weights):
                raise ValueError(
                    f"{field_name} must contain finite non-negative weights"
                )
            if abs(sum(weights) - 1.0) > 1e-9:
                raise ValueError(f"{field_name} weights must sum to 1")
            object.__setattr__(self, field_name, weights)


CONFIG = Config()
