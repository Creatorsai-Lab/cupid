"""
User personalization model.

Single source of truth for persona fields used by all agents.
Matches the frontend `PersonalizationForm` in:
`frontend/app/(dashboard)/settings/page.tsx`.

Relationship:
- Each User has at most one personalization row.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.user import Base


class UserPersonalization(Base):
    __tablename__ = "user_personalization"

    # Mapped[uuid.UUID] tells Python's type system: "this field holds a UUID type"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True, # the unique identifier for each row
        default=uuid.uuid4, # automatically generates a new UUID `using uuid.uuid4()` when a new profile is created
    )

    # A foreign key is a column in one table that references the primary key of another table
    # ForeignKey("users.id") means: The value in this column MUST exist in the users table's id column
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,        # one profile per user
        nullable=False,
        index=True,
    )

    # Personalization fields (frontend `PersonalizationForm`)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_niche: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_goal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_intent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_age_group: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_country: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_audience: Mapped[str | None] = mapped_column(String(255), nullable=True)
    usp: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship — lets you access user.personalization or personalization.user
    user = relationship("User", backref="personalization", lazy="selectin")

    def __repr__(self) -> str:
        return f"<UserPersonalization user_id={self.user_id}>"
