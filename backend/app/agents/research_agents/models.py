from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agents.models import ContractModel as PipelineContract


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FreshnessMode(StrEnum):
    BREAKING = "breaking"
    RECENT = "recent"
    CURRENT_CYCLE = "current_cycle"
    EVERGREEN = "evergreen"  # case in which freshness not matter


class ResearchStatus(StrEnum):
    COMPLETE = "complete"
    LOW_COVERAGE = "low_coverage"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ResearchErrorType(StrEnum):
    PLANNING = "planning"
    SEARCH = "search"
    EXTRACTION = "extraction"
    VALIDATION = "validation"
    EVALUATION = "evaluation"
    TIMEOUT = "timeout"
    INSUFFICIENT_COVERAGE = "insufficient_coverage"


class PersonaContext(ContractModel):
    bio: str | None = None
    niches: tuple[str, ...] = ()
    tone: str | None = None
    audience: str | None = None
    content_intent: str | None = None


class ResearchBrief(ContractModel):
    topic: str = Field(min_length=1)
    main_keywords: tuple[str, ...] = ()
    user_goal: str = Field(min_length=1)
    required_angles: tuple[str, ...] = Field(min_length=1, max_length=8)
    locale: str | None = None
    language: str = Field(default="en", min_length=2)
    freshness_mode: FreshnessMode = FreshnessMode.RECENT
    freshness_window_days: int | None = Field(default=90, ge=1)
    constraints: tuple[str, ...] = ()
    search_query_count: int = Field(default=3, ge=3, le=5)

    @model_validator(mode="after")
    def evergreen_has_no_window(self) -> "ResearchBrief":
        # A window on an evergreen brief would leak into query lanes and date-filter search.
        if self.freshness_mode == FreshnessMode.EVERGREEN:
            self.freshness_window_days = None
        return self


class PlannedQuery(ContractModel):
    id: str = Field(min_length=1)
    query: str = Field(min_length=1, max_length=300)
    purpose: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    freshness_window_days: int | None = Field(default=None, ge=1)
    preferred_source_type: str | None = None


class BackupQuery(ContractModel):
    """A spare search the planner writes for one required angle, used only if it stays uncovered."""

    angle: str = Field(min_length=1)
    query: str = Field(min_length=1, max_length=300)


class ResearchPlan(ContractModel):
    brief: ResearchBrief
    queries: tuple[PlannedQuery, ...] = Field(min_length=3, max_length=5)
    # Written in the planning call so coverage recovery needs no second LLM call.
    backup_queries: tuple[BackupQuery, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def query_ids_are_unique(self) -> "ResearchPlan":
        if len({query.id for query in self.queries}) != len(self.queries):
            raise ValueError("planned query IDs must be unique")
        return self


class CandidatePage(ContractModel):
    id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    canonical_url: str = Field(min_length=1)
    publisher_domain: str = Field(min_length=1)
    search_provider: str = Field(min_length=1)
    title: str = Field(min_length=1)
    snippet: str = ""
    published_at: datetime | None = None
    discovered_by: tuple[str, ...] = ()
    search_rank: int = Field(ge=1)


class ExtractedDocument(ContractModel):
    candidate_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    title: str | None = None
    published_at: datetime | None = None
    extraction_provider: str = Field(min_length=1)
    article_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PageRankInput(ContractModel):
    candidate_id: str = Field(min_length=1)
    title: str
    ranking_view: str
    published_at: datetime | None = None


class PageRank(ContractModel):
    """One structured LLM evaluation, keyed by stable candidate identity."""

    candidate_id: str = Field(min_length=1)
    relevance: float = Field(ge=0, le=10)
    freshness: float = Field(ge=0, le=10)
    authority: float = Field(ge=0, le=10)
    content_quality: float = Field(ge=0, le=10)
    persona_utility: float = Field(ge=0, le=10)
    covered_angles: tuple[str, ...] = ()
    justification: str = Field(min_length=1)


class PageRankBatch(ContractModel):
    """Validated evaluator response; page material is supplied separately."""

    evaluations: tuple[PageRank, ...] = Field(min_length=1)


class PageScores(ContractModel):
    relevance: float = Field(ge=0, le=10)
    freshness: float = Field(ge=0, le=10)
    authority: float = Field(ge=0, le=10)
    information_density: float = Field(ge=0, le=10)
    persona_utility: float = Field(ge=0, le=10)
    novelty: float = Field(ge=0, le=10)
    content_quality: float | None = Field(default=None, ge=0, le=10)
    composite: float | None = Field(default=None, ge=0, le=10)
    # Multiplier (0..1) applied to information_density for link/navigation/listing/repetition
    # structure. 1.0 means no structural penalty.
    structural_quality: float | None = Field(default=None, ge=0, le=1)
    # False when no publication date could be found and freshness relied on content only.
    freshness_known: bool | None = None
    rationale: str | None = None


class EvaluatedPage(ContractModel):
    candidate: CandidatePage
    content: str = Field(min_length=1)
    ranking_view: str = ""
    article_type: str | None = None
    extraction_quality: float = Field(ge=0, le=1)
    scores: PageScores | None = None
    covered_angles: tuple[str, ...] = ()
    accepted: bool
    rejection_reason: str | None = None
    media: list[str] | None = None


class FinalCorpus(ContractModel):
    title: str
    url: str
    content: str
    media: list[str] | None = None


class RunAudit(ContractModel):
    """Audit trail of one run: which provider served each stage, stage timings, per-URL
    rejection codes and non-fatal notes. Kept apart from the corpus so the composer never sees it."""

    provider_usage: dict[str, str] = Field(default_factory=dict)
    stage_timings_seconds: dict[str, float] = Field(default_factory=dict)
    rejection_reasons: dict[str, str] = Field(default_factory=dict)
    # Non-fatal observations per URL (e.g. freshness_unknown, structural penalties) that
    # lowered a page's score without removing it from the pipeline, and per failed query
    # ("query:<id>") the exception behind its stable search_error code.
    notes: dict[str, str] = Field(default_factory=dict)
    coverage_status: str | None = None
    gap_search_used: bool = False


class ResearchResult(ContractModel):
    corpus: tuple[FinalCorpus, ...] = ()
    brief: ResearchBrief | None = None
    plan: ResearchPlan | None = None
    # Every page the search stage discovered, including ones later rejected; the
    # rejection reason for each URL lives in diagnostics.rejection_reasons.
    search_results: tuple[CandidatePage, ...] = ()
    evaluated_pages: tuple[EvaluatedPage, ...] = ()
    run_audit: RunAudit = Field(default_factory=RunAudit)
    status: ResearchStatus
    error_type: ResearchErrorType | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def completed_results_have_context(self) -> "ResearchResult":
        if self.status in {ResearchStatus.COMPLETE, ResearchStatus.LOW_COVERAGE}:
            if self.brief is None or self.plan is None:
                raise ValueError(
                    "complete and low_coverage results require a brief and plan"
                )
        return self

    def composer_corpus(self) -> list[FinalCorpus]:
        return list(self.corpus)


# ── Pipeline contract: what the research step hands to the rest of Cupid ──
# Frozen (Cupid's ContractModel), unlike the agent's internal models above.


class Source(PipelineContract):
    id: str = Field(min_length=1)  # "S1", "S2", … referenced by facts and pieces
    title: str
    url: str
    published_at: datetime | None = None


class SourceDocument(PipelineContract):
    source_id: str
    content: str


class ResearchPack(PipelineContract):
    status: Literal["complete", "low_coverage", "timeout", "failed", "skipped"]
    sources: tuple[Source, ...] = ()
    documents: tuple[SourceDocument, ...] = ()

    @model_validator(mode="after")
    def _unique_source_ids(self) -> "ResearchPack":
        ids = [s.id for s in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source ids must be unique")
        return self
