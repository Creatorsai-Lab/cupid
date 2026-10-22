"""The seam between Cupid and the research agent.

- `persona_for`: the creator's profile reduced to what research needs. Name,
  nickname and USP never leave Cupid (decision D6).
- `to_pack`: the agent's ResearchResult becomes the pipeline's ResearchPack,
  sources numbered S1, S2, ... Research without a usable source raises
  StepFailedError: the step is retried, and after the last attempt the user
  sees RESEARCH_FAILED.
- `degradation_issues`: when the agent fell back to its simpler offline method
  (every provider failed for a reason other than quota), the run is labelled
  degraded instead of looking complete.
"""

from typing import Literal

from app.agents.models import CreatorProfile, Issue, RunRequest
from app.agents.research_agents.models import (
    PersonaContext,
    ResearchPack,
    ResearchResult,
    ResearchStatus,
    Source,
    SourceDocument,
)
from app.agents.runtime.retry import StepFailedError

RESEARCH_FAILED = "Research failed. Please try again."

_OFFLINE = "deterministic_fallback"  # the agent's provider_usage value for it
_DEGRADED = Issue(
    step="research",
    severity="degraded",
    message="Research used a simpler fallback method, so sources may be less relevant.",
)
_PACK_STATUS: dict[ResearchStatus, Literal["complete", "low_coverage", "timeout"]] = {
    ResearchStatus.COMPLETE: "complete",
    ResearchStatus.LOW_COVERAGE: "low_coverage",
    ResearchStatus.TIMEOUT: "timeout",
}


def persona_for(request: RunRequest, profile: CreatorProfile | None) -> PersonaContext:
    if profile is None:
        return PersonaContext(tone=request.tone)
    niche = _clean(profile.content_niche)
    audience = "; ".join(
        part
        for part in (
            _clean(profile.target_audience),
            _labelled("age", profile.target_age_group),
            _labelled("in", profile.target_country),
        )
        if part
    )
    return PersonaContext(
        bio=_clean(profile.bio),
        niches=(niche,) if niche else (),
        tone=request.tone,
        audience=audience or None,
        content_intent=_clean(profile.content_intent) or _clean(profile.content_goal),
    )


def to_pack(result: ResearchResult) -> ResearchPack:
    status = _PACK_STATUS.get(result.status)
    if status is None or not result.corpus:
        raise StepFailedError(RESEARCH_FAILED)
    published = {
        page.candidate.url: page.candidate.published_at
        for page in result.evaluated_pages
    }
    sources: list[Source] = []
    documents: list[SourceDocument] = []
    for number, item in enumerate(result.corpus, start=1):
        source_id = f"S{number}"
        sources.append(
            Source(
                id=source_id,
                title=item.title,
                url=item.url,
                published_at=published.get(item.url),
            )
        )
        documents.append(SourceDocument(source_id=source_id, content=item.content))
    return ResearchPack(
        status=status, sources=tuple(sources), documents=tuple(documents)
    )


def degradation_issues(result: ResearchResult) -> list[Issue]:
    usage = result.run_audit.provider_usage
    if _OFFLINE in (usage.get("planning"), usage.get("evaluation")):
        return [_DEGRADED]
    return []


def _clean(value: str | None) -> str | None:
    return (value or "").strip() or None


def _labelled(label: str, value: str | None) -> str | None:
    cleaned = _clean(value)
    return f"{label} {cleaned}" if cleaned else None
