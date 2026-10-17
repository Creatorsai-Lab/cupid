"""The run record: who owns a run and where it stands.

The run's full state lives in the checkpointer (one LangGraph thread per run,
thread_id = this id); this table holds what the API needs without touching the
checkpointer: ownership (events, resume), status for the UI, and created_at
for plan limits (runs per day).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, get_args

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.agents.models import RunStatus
from app.core.db import Base

STATUSES = get_args(RunStatus)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    request: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Safe to show the user; internal details go to the logs only.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in STATUSES) + ")",
            name="ck_agent_runs_status",
        ),
        # "this user's runs, newest first" and runs-per-day plan limits
        Index("ix_agent_runs_user_created", "user_id", "created_at"),
    )
