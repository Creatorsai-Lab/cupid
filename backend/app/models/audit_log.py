"""
AuditLog — an append-only record of sensitive admin actions.

WHY
───
"Who changed this user's tier on June 9th, and from what to what?" is a
question you cannot answer after the fact unless you recorded it AT the time.
Every admin-initiated state change writes one row here. Rows are only ever
INSERTed — never updated or deleted — so the trail can't be quietly rewritten.

This is intentionally generic (action + target + before/after JSON) so it can
audit more than tier changes later without a schema change.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # WHO did it (the admin). Nullable for system/automated actions (e.g. a
    # Stripe webhook in v2, or the signup default-tier write).
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # WHAT happened — a stable verb, e.g. "tier.set".
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # WHOM/WHAT it acted on.
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # before/after snapshots + any extra context, as JSON.
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.target_type}:{self.target_id}>"
