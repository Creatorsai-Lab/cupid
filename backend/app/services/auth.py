"""
Authentication service — user lookups for the auth layer.

Sign-in is Google-only (see routers/oauth_google.py), so password helpers were
removed. This keeps the one lookup the login flow needs.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Look up a user by email. Returns None if not found."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()
