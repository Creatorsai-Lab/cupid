"""Shared contracts for the agent pipeline.

The request options below are the only Python definition; the router, the
pipeline state and the agents import them from here. frontend/lib/api.ts
mirrors them, and tests/agents/test_request_options.py keeps the two equal.

Contracts are frozen: once a step writes a value it cannot be changed, only
replaced by the step that owns it (see state.py).
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ── Request options ────────────────────────────────────────────

ContentType = Literal["Text", "Image", "Article", "Video", "Ads", "Quiz"]

Platform = Literal["Twitter", "LinkedIn", "Instagram", "Facebook", "YouTube", "Web"]

ContentLength = Literal["Short", "Medium", "Long", "Full Article"]

Tone = Literal[
    "Casual",
    "Formal",
    "Informative",
    "GenZ",
    "Factual",
    "Hook First",
    "Data Driven",
    "Story Led",
    "Lifestyle",
    "Inspirational",
]


class ContractModel(BaseModel):
    """Base for pipeline contracts: immutable, and unknown fields are errors."""

    model_config = ConfigDict(frozen=True, extra="forbid")


# ── Run inputs (written once when the run starts) ──────────────


class RunRequest(ContractModel):
    run_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    content_type: ContentType
    platform: Platform
    length: ContentLength
    tone: Tone


class CreatorProfile(ContractModel):
    """Snapshot of the creator's profile at run start (profile/models.py)."""

    name: str | None = None
    nickname: str | None = None
    bio: str | None = None
    content_niche: str | None = None
    content_goal: str | None = None
    content_intent: str | None = None
    target_age_group: str | None = None
    target_country: str | None = None
    target_audience: str | None = None
    usp: str | None = None


# ── Outputs and progress ───────────────────────────────────────


class Issue(ContractModel):
    """Something a step wants the user or the logs to know; never hidden."""

    step: str
    severity: Literal["warning", "degraded", "error"]
    message: str


RunStatus = Literal["queued", "running", "completed", "degraded", "failed", "blocked"]

EventType = Literal[
    "run.started",
    "step.started",
    "step.finished",
    "research.sources",
    "piece.ready",
    "run.degraded",
    "run.failed",
    "run.completed",
]


class RunEvent(ContractModel):
    """One progress update streamed to the browser."""

    run_id: str
    type: EventType
    step: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
