"""
Profile service — CRUD operations for user persona data.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import UserProfile


async def get_profile_by_user_id(
    db: AsyncSession, user_id: uuid.UUID
) -> UserProfile | None:
    """Get a user's profile."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def upsert_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    bio: str | None,
    field: str | None,
    skills: str | None,
    geography: str | None,
    audience: str | None,
) -> UserProfile:
    """
    Create or update a user's profile (upsert pattern).
    
    Why upsert? The first time a user saves, no profile exists (CREATE).
    Every time after, we UPDATE the existing profile. Upsert handles both
    cases in one function — cleaner than separate create/update endpoints.
    """
    profile = await get_profile_by_user_id(db, user_id)

    if profile:
        # Update existing
        profile.bio = bio
        profile.field = field
        profile.skills = skills
        profile.geography = geography
        profile.audience = audience
    else:
        # Create new
        profile = UserProfile(
            user_id=user_id,
            bio=bio,
            field=field,
            skills=skills,
            geography=geography,
            audience=audience,
        )
        db.add(profile)

    await db.commit()
    await db.refresh(profile)
    return profile
