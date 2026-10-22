"""
Authentication service — user lookups for the auth layer.

Sign-in is Google or phone OTP (see app/auth/router.py); there are no password
helpers. These are the lookups those login flows need.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import LoginEvent, User
from app.core.client_ip import client_ip


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Look up a user by email. Returns None if not found."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_phone(db: AsyncSession, phone: str) -> User | None:
    """Look up a user by normalized phone (see app/auth/otp.normalize_phone)."""
    result = await db.execute(select(User).where(User.phone == phone))
    return result.scalar_one_or_none()


def link_google_identity(user: User, info: dict[str, Any]) -> None:
    user.auth_provider = "google"
    user.provider_account_id = str(info["sub"])
    user.avatar_url = str(info["picture"]) if info.get("picture") else None
    if info.get("name"):
        user.full_name = str(info["name"])
    user.hashed_password = None


async def record_login(
    db: AsyncSession, user: User, method: str, request: Request
) -> None:
    """Add a row to the user's login history (Settings > Login history)."""
    user_agent = request.headers.get("user-agent")
    db.add(
        LoginEvent(
            user_id=user.id,
            method=method,
            ip_address=client_ip(request)[:45],
            user_agent=user_agent[:512] if user_agent else None,
        )
    )
    await db.commit()


async def list_logins(
    db: AsyncSession, user_id: uuid.UUID, limit: int
) -> Sequence[LoginEvent]:
    """The user's most recent sign-ins, newest first."""
    result = await db.execute(
        select(LoginEvent)
        .where(LoginEvent.user_id == user_id)
        .order_by(LoginEvent.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
