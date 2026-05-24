"""
CreationHistory model — stores a completed content-generation run.

═══════════════════════════════════════════════════════════════════════════
WHAT GETS SAVED
═══════════════════════════════════════════════════════════════════════════
One row per completed creation. We store:
    - the user's original prompt
    - the platform + tone they chose
    - the 3 generated variants (as JSONB)

We do NOT store intermediate pipeline state (research data, personalization
queries, sources). The history view only shows the prompt and the final
posts, so storing the rest would be dead weight.

═══════════════════════════════════════════════════════════════════════════
WHY JSONB FOR VARIANTS
═══════════════════════════════════════════════════════════════════════════
The 3 variants are always read and written together as one unit — never
queried individually ("find me all hook_first variants" is not a use case).
Storing them as a single JSONB column means:
    - one row per creation (simple, fast)
    - no join needed to render a history card
    - schema flexibility if a variant gains a field later

This is the same "flexible blob" pattern used in insights_snapshots.raw_data.
Each variant in the array looks like:
    {"angle": "hook_first", "platform": "LinkedIn",
     "content": "...", "char_count": 847}
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.user import Base

if TYPE_CHECKING:
    from app.models.user import User


class CreationHistory(Base):
    __tablename__ = "creation_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The user's original request
    prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # Generation settings (for display + future filtering)
    target_platform: Mapped[str] = mapped_column(String(32), default="All")
    tone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # The 3 generated variants, stored as a JSON array
    variants: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="creation_history")

    __table_args__ = (
        # Common query: "this user's history, newest first"
        Index("ix_history_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<CreationHistory {self.user_id}/{self.prompt[:30]!r}>"