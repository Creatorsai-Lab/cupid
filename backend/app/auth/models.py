"""User database model. This class maps to the 'users' table in PostgreSQL.
Each attribute becomes a column."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.connections.models import SocialConnection
    from app.history.models import CreationHistory


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Nullable: phone-login users have no email. Every account has an email
    # or a phone (ck_users_email_or_phone).
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    # Digits with country code, no "+" (e.g. 919999999999). Set by phone login.
    phone: Mapped[str | None] = mapped_column(
        String(15), unique=True, nullable=True, index=True
    )
    # Nullable: social-login users have no password.
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Identity provider this account authenticates with.
    auth_provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="google"
    )
    provider_account_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
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

    __table_args__ = (
        CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL", name="ck_users_email_or_phone"
        ),
    )

    # __repr__ for debug print User object.
    def __repr__(self) -> str:
        return f"<User {self.email or self.phone}>"


class LoginEvent(Base):
    """One successful sign-in. Shown to the user as their login history."""

    __tablename__ = "login_history"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # "google" or "phone".
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    # 45 chars fits any IPv6 text form. See app/core/client_ip.py.
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        # The only query: "this user's logins, newest first".
        Index("ix_login_history_user_created", "user_id", "created_at"),
    )
