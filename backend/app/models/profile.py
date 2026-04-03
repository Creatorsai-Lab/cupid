"""
UserProfile model — stores persona/personalization data.

This is a one-to-one relationship with User:
  - Each User has exactly one UserProfile
  - The profile stores data used by the Persona Agent

Database: cupid_db
  ├── Table: users
  │     ├── id (UUID, primary key)
  │     ├── full_name
  │     ├── email
  │     └── hashed_password
  └── Table: user_profiles
        ├── id (UUID, primary key)
        ├── user_id (foreign key → users.id)
        ├── bio
        ├── field
        └── skills

"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.user import Base


class UserProfile(Base):
    # __tablename__ tells SQLAlchemy: "When this Python class is converted to a database table, name it user_profiles
    __tablename__ = "user_profiles"

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

    # Persona fields — used by the AI agents
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    skills: Mapped[str | None] = mapped_column(Text, nullable=True)
    geography: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audience: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship — lets you access user.profile or profile.user
    user = relationship("User", backref="profile", lazy="selectin")

    def __repr__(self) -> str:
        return f"<UserProfile user_id={self.user_id}>"
