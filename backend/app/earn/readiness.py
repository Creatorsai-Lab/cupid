"""
app/earn/readiness.py
═══════════════════════════════════════════════════════════════════════════

The decision engine. Given a tier assessment (can they?) and the Q&A answers
(do they want to?), produce — for every stream — a single state that drives
the whole page, plus a ranked list of the creator's best next moves.

This is the most important pure-logic file in the feature. Like tiers.py it
does no I/O: assessment + answers in, a structured report out. That makes the
product's core advice fully unit-testable with plain assertions.

THE TWO ORTHOGONAL AXES
───────────────────────
  ELIGIBILITY  — can they realistically do this? Derived from audience size
                 (with a documented, narrow engagement adjustment).
  INTEREST     — do they want to? Straight from the mandatory Q&A.

Crossing them gives each stream a STATE. The states are designed so we NEVER
tell a creator to "start" something they told us they already do, and never
clutter the page with streams they said they don't want.

  ┌─────────────┬──────────────────┬─────────────────────┐
  │             │ eligible/emerging│  locked             │
  ├─────────────┼──────────────────┼─────────────────────┤
  │ already doing│ OPTIMIZE         │ OPTIMIZE (trust them)│
  │ wants to    │ GREEN_LIGHT /    │ FOUNDATION          │
  │             │ ALMOST_THERE     │                     │
  │ not interested│ SUPPRESSED      │ SUPPRESSED          │
  └─────────────┴──────────────────┴─────────────────────┘
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.earn.config import Tier
from app.earn.streams import (
    INTEREST_DOING,
    INTEREST_NO,
    INTEREST_WANT,
    RevenueStream,
    StreamCategory,
    all_streams,
)
from app.earn.tiers import TierAssessment


# ─────────────────────────────────────────────────────────────────────────
#  Tunables specific to readiness (kept here, not config.py, because they're
#  about the eligibility *logic*, not the tier *bands*)
# ─────────────────────────────────────────────────────────────────────────

# A creator within this fraction of a stream's follower floor is "emerging" —
# close enough that the right message is "almost there", not "locked".
# 0.7 → within 70% of the requirement.
EMERGING_FRACTION: float = 0.7


# ─────────────────────────────────────────────────────────────────────────
#  Enums for the two axes and the resulting state
# ─────────────────────────────────────────────────────────────────────────

class Eligibility(str, Enum):
    ELIGIBLE = "eligible"    # meets the floor — go
    EMERGING = "emerging"    # within EMERGING_FRACTION of the floor — almost
    LOCKED = "locked"        # not yet — needs real growth first


class StreamState(str, Enum):
    """The single state per stream that the UI renders from."""
    GREEN_LIGHT = "green_light"    # wants it + eligible → the headline: go, here are opps
    ALMOST_THERE = "almost_there"  # wants it + emerging → here's the gap to close
    FOUNDATION = "foundation"      # wants it + locked → not yet, build this first
    OPTIMIZE = "optimize"          # already doing it → tips to do it better, never "start"
    SUPPRESSED = "suppressed"      # not interested → hidden from the page entirely


# ─────────────────────────────────────────────────────────────────────────
#  Output records
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StreamReadiness:
    """Everything the UI needs to render one stream's card."""
    stream_id: str
    label: str
    category: str
    durability: str
    effort: str
    eligibility: Eligibility
    interest: str                 # doing / want / no
    state: StreamState
    tradeoff_label: str
    short_pitch: str
    time_to_first_revenue: str
    min_followers: int
    followers_gap: int            # how many more followers to reach the floor (0 if met)


@dataclass(frozen=True)
class ReadinessReport:
    """The complete computed picture — input to opportunities, coach, and the API."""
    tier: Tier
    assessment: TierAssessment
    # All non-suppressed streams, in canonical journey order (for the grid view).
    streams: tuple[StreamReadiness, ...]
    # The creator's best next moves: GREEN_LIGHT + ALMOST_THERE, ranked. (Section 2/3.)
    ranked_gaps: tuple[StreamReadiness, ...]
    # Streams they're already doing (Section 2 "keep optimizing").
    optimizing: tuple[StreamReadiness, ...]
    # Streams they want but can't reach yet (Section 2 "grow toward").
    foundation: tuple[StreamReadiness, ...]


# ─────────────────────────────────────────────────────────────────────────
#  Eligibility
# ─────────────────────────────────────────────────────────────────────────

def _base_eligibility(followers: int, min_followers: int) -> Eligibility:
    """Raw eligibility from follower count vs. the stream's floor."""
    if followers >= min_followers:
        return Eligibility.ELIGIBLE
    if min_followers > 0 and followers >= int(min_followers * EMERGING_FRACTION):
        return Eligibility.EMERGING
    return Eligibility.LOCKED


def _apply_flex(
    base: Eligibility,
    stream: RevenueStream,
    assessment: TierAssessment,
) -> Eligibility:
    """
    Let the engagement flex nudge eligibility by one notch — but ONLY for
    brand-facing (content-influenced) streams.

    WHY ONLY BRAND-FACING STREAMS:
    A brand deciding whether to sponsor you weighs engagement heavily — a
    punchy 5K account with viral reach genuinely IS a better bet than a
    dormant 15K one, so flexing their brand-deal eligibility is realistic.
    But streams where the creator sells to their OWN audience (a paid
    community, digital products) depend on audience size and willingness to
    pay, which engagement ratio doesn't change the same way. And platform
    ad revenue is a hard threshold the platform sets — engagement can't flex
    it. So we confine the flex to where it reflects how a real gatekeeper
    actually decides.
    """
    if stream.category != StreamCategory.CONTENT_INFLUENCED:
        return base

    if assessment.flex == 1 and base == Eligibility.EMERGING:
        # Punching above weight → engagement compensates for raw reach.
        return Eligibility.ELIGIBLE
    if assessment.flex == -1 and base == Eligibility.ELIGIBLE:
        # Dormant audience → weaker brand appeal than the raw number suggests.
        return Eligibility.EMERGING
    return base


def _eligibility_for(stream: RevenueStream, assessment: TierAssessment) -> Eligibility:
    base = _base_eligibility(assessment.signals.total_followers, stream.min_followers)
    return _apply_flex(base, stream, assessment)


# ─────────────────────────────────────────────────────────────────────────
#  The state machine: (eligibility × interest) → state
# ─────────────────────────────────────────────────────────────────────────

def _state_for(eligibility: Eligibility, interest: str) -> StreamState:
    """
    Combine the two axes into the single state the UI renders.

    Note the deliberate asymmetry on 'already doing': we honor it regardless
    of our eligibility read. If a creator says they're doing affiliate but our
    follower data says 'locked', we DON'T contradict them — they know their
    own business better than our inference does. We show OPTIMIZE, not a
    condescending 'you're not ready for this'.
    """
    if interest == INTEREST_NO:
        return StreamState.SUPPRESSED

    if interest == INTEREST_DOING:
        return StreamState.OPTIMIZE  # trust the creator, offer to help them improve

    # interest == WANT
    if eligibility == Eligibility.ELIGIBLE:
        return StreamState.GREEN_LIGHT
    if eligibility == Eligibility.EMERGING:
        return StreamState.ALMOST_THERE
    return StreamState.FOUNDATION


# ─────────────────────────────────────────────────────────────────────────
#  Gap ranking
# ─────────────────────────────────────────────────────────────────────────

# Lower sort-key sorts first. These encode the ranking PRIORITY:
#   1. green lights before almost-theres (actionable now beats almost)
#   2. quick wins before heavy lifts (low effort first)
#   3. durability ONLY as a final tiebreaker (the 'balanced' decision: we
#      nudge toward recurring income but never let it dominate the order)
_STATE_RANK = {StreamState.GREEN_LIGHT: 0, StreamState.ALMOST_THERE: 1}
_EFFORT_RANK = {"low": 0, "medium": 1, "high": 2}
_DURABILITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _gap_sort_key(sr: StreamReadiness) -> tuple[int, int, int]:
    return (
        _STATE_RANK.get(sr.state, 99),
        _EFFORT_RANK.get(sr.effort, 99),
        _DURABILITY_RANK.get(sr.durability, 99),  # tiebreaker only
    )


# ─────────────────────────────────────────────────────────────────────────
#  Public entry point
# ─────────────────────────────────────────────────────────────────────────

def build_readiness(
    assessment: TierAssessment,
    answers: dict[str, str],
) -> ReadinessReport:
    """
    The single public function: tier assessment + Q&A answers → full report.

    `answers` is the validated {stream_id: interest} map from the EarnProfile.
    Any stream missing from `answers` is treated as 'not interested' (defensive
    — a complete map is enforced at the API boundary, but we never crash here).
    """
    followers = assessment.signals.total_followers

    per_stream: list[StreamReadiness] = []
    for stream in all_streams():
        interest = answers.get(stream.id, INTEREST_NO)
        eligibility = _eligibility_for(stream, assessment)
        state = _state_for(eligibility, interest)

        gap = max(0, stream.min_followers - followers)

        per_stream.append(
            StreamReadiness(
                stream_id=stream.id,
                label=stream.label,
                category=stream.category.value,
                durability=stream.durability.value,
                effort=stream.effort.value,
                eligibility=eligibility,
                interest=interest,
                state=state,
                tradeoff_label=stream.tradeoff_label,
                short_pitch=stream.short_pitch,
                time_to_first_revenue=stream.time_to_first_revenue,
                min_followers=stream.min_followers,
                followers_gap=gap,
            )
        )

    # Partition into the buckets the sections need.
    visible = tuple(s for s in per_stream if s.state != StreamState.SUPPRESSED)
    gaps = tuple(
        sorted(
            (s for s in per_stream if s.state in (StreamState.GREEN_LIGHT, StreamState.ALMOST_THERE)),
            key=_gap_sort_key,
        )
    )
    optimizing = tuple(s for s in per_stream if s.state == StreamState.OPTIMIZE)
    foundation = tuple(s for s in per_stream if s.state == StreamState.FOUNDATION)

    return ReadinessReport(
        tier=assessment.tier,
        assessment=assessment,
        streams=visible,
        ranked_gaps=gaps,
        optimizing=optimizing,
        foundation=foundation,
    )