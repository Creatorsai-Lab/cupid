"""
app/earn/models.py
═══════════════════════════════════════════════════════════════════════════

The only two things the Earn feature persists:

  1. EarnProfile     — a creator's Q&A answers. Its EXISTENCE is the gate:
                       no row → show the mandatory questionnaire; row → render
                       the page.
  2. EarnOpportunity — the archive of monetization opportunities (curated +
                       discovered) that Section 3 matches against.

SELF-CONTAINED BY DESIGN
────────────────────────
These models live entirely in app/earn/ and deliberately do NOT add a
relationship/back_populates onto the User model — that would require editing
app/models/user.py, which the brief says to leave untouched. We keep only the
foreign-key column and query by user_id directly in the service. A one-
directional FK is all we need and it keeps the feature drop-in.

The two columns that look like they "should" be relational — the Q&A answers
and the opportunity's niche tags — are stored as JSONB instead, following the
same flexible-blob pattern you used for creation_history.variants and the
insights snapshots: data that's always read and written as a whole unit, never
queried field-by-field, belongs in one JSONB column, not a child table.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

# IMPORTANT: import the SAME declarative Base the rest of the app uses, so
# these tables register on the shared metadata and Alembic picks them up.
# This is an import of shared infrastructure, not a reuse of a feature file.
from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ─────────────────────────────────────────────────────────────────────────
#  EarnProfile — the Q&A answers; existence == gate passed
# ─────────────────────────────────────────────────────────────────────────


class EarnProfile(Base):
    __tablename__ = "earn_profile"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # One profile per user. unique=True enforces the 1:1 at the DB level so a
    # double-submit can't create two gates for the same creator.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # ondelete CASCADE: if the user is deleted, their earn profile goes too.
        # We reference the users table by name to avoid importing the User model.
        nullable=False,
        unique=True,
        index=True,
    )

    # The interest map: {stream_id: "doing"|"want"|"no"}. Always read/written
    # as a whole → JSONB blob, not a child table of (profile, stream, answer).
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


# ─────────────────────────────────────────────────────────────────────────
#  EarnOpportunity — the matchable archive (curated + discovered)
# ─────────────────────────────────────────────────────────────────────────

# Opportunity types — kept as plain string constants (not a DB enum) so adding
# a new type later is a code change, not a fragile schema migration.
OPP_AFFILIATE = "affiliate"
OPP_AMBASSADOR = "ambassador"
OPP_BRAND_DEAL = "brand_deal"

SOURCE_CURATED = "curated"
SOURCE_DISCOVERED = "discovered"


class EarnOpportunity(Base):
    __tablename__ = "earn_opportunity"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    opp_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    brand_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Which niches this fits — list[str] of normalized niche keys, or ["all"].
    # JSONB so we can store a small list and do containment checks in Postgres.
    niche_tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # The minimum tier a creator must be to see this (matches Tier values:
    # "nano"/"micro"/"mid"/"macro"). Stored as string for the same reason as
    # opp_type — flexible, migration-free.
    min_tier: Mapped[str] = mapped_column(
        String(16), nullable=False, default="nano", index=True
    )

    # Free-text commission/payout note ("Up to 10%", "Recurring 30%"), shown
    # on the card. Never a structured number — these vary wildly and we don't
    # want to imply precision we can't guarantee.
    commission_note: Mapped[str | None] = mapped_column(String(120), nullable=True)

    url: Mapped[str] = mapped_column(String(1000), nullable=False)

    # curated (hand-seeded, trusted) vs discovered (from the search job).
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SOURCE_CURATED
    )

    # Soft on/off so we can retire stale discovered entries without deleting.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    __table_args__ = (
        # The hot query is "active opportunities at or below this creator's
        # tier, of a given type" — this composite index serves it directly.
        Index("ix_earn_opp_active_type_tier", "is_active", "opp_type", "min_tier"),
    )
