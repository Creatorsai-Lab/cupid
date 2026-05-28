"""
app/earn/schemas.py
═══════════════════════════════════════════════════════════════════════════

Pydantic request/response contracts for the Earn API. These define the exact
shape the frontend receives, decoupled from the internal dataclasses
(TierAssessment, ReadinessReport, ...). Keeping a separate API layer means we
can refactor the engine's internals without breaking the client.

The readiness response is organized to mirror the four page sections 1:1, so
the frontend can map section → component with no reshaping.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────
#  Q&A gate
# ─────────────────────────────────────────────────────────────────────────

class QuestionOption(BaseModel):
    value: str          # "want" | "doing" | "no"
    label: str          # human-facing


class EarnQuestionOut(BaseModel):
    stream_id: str
    question: str
    options: list[QuestionOption]


class QuestionsResponse(BaseModel):
    questions: list[EarnQuestionOut]


class ProfileSubmitRequest(BaseModel):
    # {stream_id: "want"|"doing"|"no"} — completeness/validity enforced in the
    # router against the taxonomy before persisting.
    answers: dict[str, str]


class ProfileResponse(BaseModel):
    exists: bool
    answers: dict[str, str] = Field(default_factory=dict)
    updated_at: datetime | None = None


# ─────────────────────────────────────────────────────────────────────────
#  Section 1 — stats snapshot
# ─────────────────────────────────────────────────────────────────────────

class StatsSnapshot(BaseModel):
    total_followers: int
    monthly_views: int
    total_posts: int
    connected_platforms: int
    tier: str                       # nano/micro/mid/macro
    tier_label: str                 # "Micro creator"
    tier_blurb: str
    confidence: str                 # high/low
    engagement_note: str | None = None   # the flex reason, if any
    has_data: bool


# ─────────────────────────────────────────────────────────────────────────
#  Section 2 — eligibility verdict
# ─────────────────────────────────────────────────────────────────────────

class StreamCard(BaseModel):
    stream_id: str
    label: str
    category: str
    durability: str
    effort: str
    eligibility: str                # eligible/emerging/locked
    interest: str                   # want/doing/no
    state: str                      # green_light/almost_there/foundation/optimize
    tradeoff_label: str
    short_pitch: str
    time_to_first_revenue: str
    followers_gap: int              # 0 if already eligible


class EligibilityVerdict(BaseModel):
    coach_summary: str              # LLM narrative grounded in the computed report
    green_lights: list[StreamCard]  # ranked best moves (eligible + wanted)
    almost_there: list[StreamCard]  # emerging + wanted
    optimizing: list[StreamCard]    # already doing
    foundation: list[StreamCard]    # wanted but locked


# ─────────────────────────────────────────────────────────────────────────
#  Section 3 — matched opportunities
# ─────────────────────────────────────────────────────────────────────────

class OpportunityOut(BaseModel):
    id: str
    opp_type: str
    title: str
    brand_name: str | None = None
    description: str | None = None
    commission_note: str | None = None
    url: str
    source: str                     # curated/discovered


class OpportunitySection(BaseModel):
    intro: str                      # e.g. "You're cleared for affiliate — here are programs to start with"
    opportunities: list[OpportunityOut]
    # When nothing matches yet, give the creator an honest, useful message
    # rather than an empty void.
    empty_message: str | None = None


# ─────────────────────────────────────────────────────────────────────────
#  Section 4 — creative niche ideas
# ─────────────────────────────────────────────────────────────────────────

class CreativeIdea(BaseModel):
    title: str                      # short headline
    idea: str                       # 1-2 sentence concrete suggestion
    related_stream: str | None = None   # which stream it supports, if any


class CreativeSection(BaseModel):
    intro: str
    ideas: list[CreativeIdea]


# ─────────────────────────────────────────────────────────────────────────
#  The full page payload
# ─────────────────────────────────────────────────────────────────────────

class ReadinessResponse(BaseModel):
    stats: StatsSnapshot
    verdict: EligibilityVerdict
    opportunities: OpportunitySection
    creative: CreativeSection
    generated_at: datetime