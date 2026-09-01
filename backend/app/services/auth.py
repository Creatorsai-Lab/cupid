"""
Authentication service — user lookups for the auth layer.

Sign-in is Google-only (see routers/oauth_google.py), so password helpers were
removed. This keeps the one lookup the login flow needs.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Look up a user by email. Returns None if not found."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


def link_google_identity(user: User, info: dict[str, Any]) -> None:
    user.auth_provider = "google"
    user.provider_account_id = str(info["sub"])
    user.avatar_url = str(info["picture"]) if info.get("picture") else None
    if info.get("name"):
        user.full_name = str(info["name"])
    user.hashed_password = None
