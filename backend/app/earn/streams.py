"""
app/earn/streams.py
═══════════════════════════════════════════════════════════════════════════

The revenue-stream taxonomy — the single source of truth for the entire
Earn feature. Every tier threshold, Q&A question, eligibility check, and
opportunity match keys off the streams defined here.

DESIGN PHILOSOPHY
─────────────────
This file is *expertise encoded as data*. It is deliberately a static
config — not a database table and not user data — because:

  1. It rarely changes (the monetization landscape shifts in months, not
     minutes), so a code-reviewed constant is safer than a mutable row.
  2. It must be reproducible. The same creator profile must always produce
     the same eligibility verdict; data that lives in code guarantees that.
  3. It is the one place a non-engineer (you, wearing the strategist hat)
     can tune the whole product's advice by editing numbers and copy.

When the market moves — a new durable stream emerges, a follower threshold
shifts — you edit THIS file and nothing else. The scoring engine, the Q&A,
and the opportunity matcher all read from here.

WHAT EACH STREAM CARRIES
────────────────────────
  • eligibility floor   → the audience size that unlocks the stream
  • durability          → recurring vs. one-off (shown as a trade-off label,
                          NOT used as a heavy ranking multiplier — per the
                          "balanced" decision, we inform, we don't push)
  • effort              → startup cost, used to surface quick wins
  • the Q&A question    → so the question set is DERIVED from the taxonomy,
                          never maintained as a separate list that can drift
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ─────────────────────────────────────────────────────────────────────────
#  Enums — small, closed vocabularies so typos become errors, not bugs
# ─────────────────────────────────────────────────────────────────────────

class StreamCategory(str, Enum):
    """
    The attribution model the research recommends: classify each stream by
    HOW it relates to the content, because that shapes the advice.
    """
    CONTENT_INFLUENCED = "content_influenced"  # affiliate, sponsorship — content drives a 3rd-party sale
    DIRECT = "direct"                           # audience pays the creator directly (the durable tier)
    PLATFORM_NATIVE = "platform_native"         # the platform itself pays (ad rev, gifts)


class Durability(str, Enum):
    """How recurring the income is. Surfaced as a label; not a ranking weight."""
    HIGH = "high"      # recurring, compounding (memberships, communities)
    MEDIUM = "medium"  # semi-recurring (digital products, ambassadorships)
    LOW = "low"        # episodic, one-off (single sponsorships)


class Effort(str, Enum):
    """Startup cost to get the first dollar. Low-effort streams = quick wins."""
    LOW = "low"        # can start today with what they have
    MEDIUM = "medium"  # needs setup (a product, a community space)
    HIGH = "high"      # needs real infrastructure / authority


# ─────────────────────────────────────────────────────────────────────────
#  The stream record
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RevenueStream:
    """
    One monetization avenue, fully described.

    frozen=True makes instances immutable — this is config, and config that
    can be accidentally mutated at runtime is a source of heisenbugs. Freezing
    it means any attempt to change a stream after definition raises loudly.
    """
    id: str                       # stable key, used everywhere (DB, Q&A answers, matching)
    label: str                    # human-facing name
    category: StreamCategory
    durability: Durability
    effort: Effort

    # Eligibility floor — total followers SUMMED across all connected
    # platforms. `min_followers` is the hard floor; below it the stream is
    # "locked". `ideal_followers` is where the stream starts paying well —
    # used to phrase "you're cleared, but this really sings at N+".
    min_followers: int
    ideal_followers: int

    time_to_first_revenue: str    # plain-language, from the timeline research
    tradeoff_label: str           # the honest one-liner shown on every card
    short_pitch: str              # one sentence: what this stream IS
    question: str                 # the Q&A question (derived set — see questions())

    # Niches where this stream over- or under-performs. None = universal.
    # These are matched loosely against the creator's normalized niche.
    niche_fit: tuple[str, ...] | None = None


# ─────────────────────────────────────────────────────────────────────────
#  THE TAXONOMY
#  Ordered roughly by the audience size at which they unlock, so reading
#  top-to-bottom traces a creator's journey from nano to macro.
# ─────────────────────────────────────────────────────────────────────────

_STREAMS: tuple[RevenueStream, ...] = (

    # ── Foundation tier: available to almost anyone, start today ──────────
    RevenueStream(
        id="affiliate",
        label="Affiliate Marketing",
        category=StreamCategory.CONTENT_INFLUENCED,
        durability=Durability.MEDIUM,
        effort=Effort.LOW,
        min_followers=0,            # genuinely no floor — works at any size
        ideal_followers=2_000,
        time_to_first_revenue="Days to weeks",
        tradeoff_label="Fast to start · income scales with trust, not just reach",
        short_pitch="Earn commission by recommending products you already use, via tracked links.",
        question="Affiliate marketing — recommending products for commission. Where are you with this?",
        niche_fit=None,
    ),
    RevenueStream(
        id="tips",
        label="Tips & Donations",
        category=StreamCategory.DIRECT,
        durability=Durability.LOW,
        effort=Effort.LOW,
        min_followers=0,
        ideal_followers=1_000,
        time_to_first_revenue="Immediate, once set up",
        tradeoff_label="Zero barrier · unpredictable, depends on audience goodwill",
        short_pitch="Let your audience support you directly with one-off tips or buy-me-a-coffee style payments.",
        question="Tips or donations — a way for fans to support you directly. Where are you with this?",
        niche_fit=None,
    ),

    # ── Activation tier: the first 'real' income, ~1K+ ───────────────────
    RevenueStream(
        id="digital_products",
        label="Digital Products",
        category=StreamCategory.DIRECT,
        durability=Durability.MEDIUM,
        effort=Effort.MEDIUM,
        min_followers=1_000,
        ideal_followers=5_000,
        time_to_first_revenue="Weeks (once the product exists)",
        tradeoff_label="You keep most of the revenue · requires building the product once",
        short_pitch="Sell templates, presets, ebooks, or guides — make once, sell repeatedly.",
        niche_fit=None,
        question="Digital products — selling templates, presets, guides, etc. Where are you with this?",
    ),
    RevenueStream(
        id="paid_community",
        label="Paid Community / Membership",
        category=StreamCategory.DIRECT,
        durability=Durability.HIGH,
        effort=Effort.MEDIUM,
        min_followers=1_000,
        ideal_followers=8_000,
        time_to_first_revenue="3–9 months to meaningful income",
        tradeoff_label="Most durable, compounding income · slower to build momentum",
        short_pitch="A recurring-revenue inner circle — exclusive content, access, or community for a monthly fee.",
        niche_fit=None,
        question="A paid community or membership — recurring monthly income. Where are you with this?",
    ),
    RevenueStream(
        id="paid_challenge",
        label="Paid Challenge / Cohort",
        category=StreamCategory.DIRECT,
        durability=Durability.MEDIUM,
        effort=Effort.MEDIUM,
        min_followers=1_000,
        ideal_followers=6_000,
        time_to_first_revenue="Weeks to first cohort",
        tradeoff_label="Fastest path to first real revenue · time-intensive to run live",
        short_pitch="A time-boxed paid program (e.g. a 7-day challenge) that turns engagement into income fast.",
        niche_fit=None,
        question="A paid challenge or cohort program — a short, paid, guided experience. Where are you with this?",
    ),

    # ── Brand tier: needs an engaged, sizeable audience ──────────────────
    RevenueStream(
        id="brand_deals",
        label="Brand Deals & Sponsorships",
        category=StreamCategory.CONTENT_INFLUENCED,
        durability=Durability.LOW,
        effort=Effort.MEDIUM,
        min_followers=5_000,        # realistic floor for paid sponsorships
        ideal_followers=25_000,
        time_to_first_revenue="Varies — depends on outreach & fit",
        tradeoff_label="Biggest single paydays · episodic and getting more competitive",
        short_pitch="Brands pay you to feature their product — the classic creator income, best as one layer of several.",
        niche_fit=None,
        question="Brand deals & sponsorships — paid partnerships with companies. Where are you with this?",
    ),
    RevenueStream(
        id="brand_ambassador",
        label="Brand Ambassadorship",
        category=StreamCategory.CONTENT_INFLUENCED,
        durability=Durability.MEDIUM,
        effort=Effort.MEDIUM,
        min_followers=5_000,
        ideal_followers=20_000,
        time_to_first_revenue="Varies — relationship-driven",
        tradeoff_label="Recurring while it lasts · ties you to one brand's reputation",
        short_pitch="An ongoing paid relationship with one brand — more stable than one-off sponsorships.",
        niche_fit=None,
        question="Brand ambassadorships — ongoing paid relationships with a brand. Where are you with this?",
    ),

    # ── Authority tier: monetize expertise, any audience size if niche is sharp
    RevenueStream(
        id="coaching",
        label="Coaching / Consulting",
        category=StreamCategory.DIRECT,
        durability=Durability.MEDIUM,
        effort=Effort.HIGH,
        min_followers=2_000,        # not about reach — about demonstrated authority
        ideal_followers=10_000,
        time_to_first_revenue="Weeks, if authority is established",
        tradeoff_label="Highest income per customer · trades your time directly for money",
        short_pitch="Sell your expertise one-to-one or one-to-few — the highest value-per-hour for skilled creators.",
        niche_fit=None,
        question="Coaching or consulting — selling your expertise directly. Where are you with this?",
    ),

    # ── Platform-native: the platform pays you ───────────────────────────
    RevenueStream(
        id="ad_revenue",
        label="Platform Ad Revenue",
        category=StreamCategory.PLATFORM_NATIVE,
        durability=Durability.MEDIUM,
        effort=Effort.LOW,
        min_followers=1_000,        # e.g. YouTube Partner Program-style thresholds
        ideal_followers=50_000,
        time_to_first_revenue="Once monetization threshold is met",
        tradeoff_label="Passive once enabled · low per-view, needs real volume",
        short_pitch="The platform shares ad income from your content once you cross its monetization bar.",
        niche_fit=None,
        question="Platform ad revenue — getting paid by the platform for views. Where are you with this?",
    ),
)


# ─────────────────────────────────────────────────────────────────────────
#  Accessors — the rest of the codebase touches the taxonomy ONLY through
#  these, never the private tuple directly. This keeps the storage shape
#  swappable without breaking callers.
# ─────────────────────────────────────────────────────────────────────────

# Index for O(1) lookups by id — built once at import.
_BY_ID: dict[str, RevenueStream] = {s.id: s for s in _STREAMS}


def all_streams() -> tuple[RevenueStream, ...]:
    """Every stream, in journey order (nano → macro)."""
    return _STREAMS


def get_stream(stream_id: str) -> RevenueStream | None:
    """One stream by id, or None if the id is unknown."""
    return _BY_ID.get(stream_id)


def stream_ids() -> tuple[str, ...]:
    """All valid stream ids — useful for validating incoming Q&A answers."""
    return tuple(_BY_ID.keys())


# ─────────────────────────────────────────────────────────────────────────
#  The Q&A question set — DERIVED from the taxonomy, never hand-maintained.
#  This is the whole point of putting `question` on the stream: the gate and
#  the engine can never disagree about which streams exist, because they read
#  the same list.
# ─────────────────────────────────────────────────────────────────────────

# The three answers every question offers. Stable keys (stored in the DB),
# human labels (shown in the UI). Keys are what the engine reasons over.
INTEREST_DOING = "doing"   # already doing it → show optimization, never "start this"
INTEREST_WANT = "want"     # wants to → eligible+want = green light
INTEREST_NO = "no"         # not interested → suppress entirely

INTEREST_OPTIONS: tuple[tuple[str, str], ...] = (
    (INTEREST_WANT, "I want to do this"),
    (INTEREST_DOING, "I'm already doing this"),
    (INTEREST_NO, "Not interested"),
)

VALID_INTERESTS: frozenset[str] = frozenset({INTEREST_DOING, INTEREST_WANT, INTEREST_NO})


@dataclass(frozen=True)
class EarnQuestion:
    """One Q&A item, ready to render in the mandatory gate."""
    stream_id: str
    question: str
    options: tuple[tuple[str, str], ...]  # (value, label) pairs


def questions() -> tuple[EarnQuestion, ...]:
    """
    The full Q&A, one item per stream, in journey order. The frontend renders
    these as the mandatory first-visit gate; the answers come back as a
    {stream_id: interest_value} map that becomes the EarnProfile.
    """
    return tuple(
        EarnQuestion(stream_id=s.id, question=s.question, options=INTEREST_OPTIONS)
        for s in _STREAMS
    )


def is_valid_answer_map(answers: dict[str, str]) -> bool:
    """
    Validate an incoming Q&A submission: every stream answered, every answer
    a legal value. Used by the router to reject malformed/partial gates —
    'mandatory' means we enforce completeness server-side, not just in the UI.
    """
    if set(answers.keys()) != set(_BY_ID.keys()):
        return False
    return all(v in VALID_INTERESTS for v in answers.values())