"""User database model. This class maps to the 'users' table in PostgreSQL.
Each attribute becomes a column."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.creation_history import CreationHistory
    from app.models.social_connection import SocialConnection


class Base(DeclarativeBase):
    """
    Base class for all ORM models. Alembic uses this Base.
    Every model in Cupid should inherit from this Base.
    """

    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Durable admin flag — the source of truth every admin gate reads. Set
    # automatically at startup for emails in settings.admin_emails (see
    # app/admin/security.bootstrap_admins). Survives the future auth switch.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    social_connections: Mapped[list["SocialConnection"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",  # if user account is deleted, eventually all social connections too
    )
    creation_history: Mapped[list["CreationHistory"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # __repr__ for debug print User object.
    def __repr__(self) -> str:
        return f"<User {self.email}>"
