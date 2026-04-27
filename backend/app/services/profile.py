"""
Profile service — CRUD operations for user personalization data.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import UserPersonalization


async def get_profile_by_user_id(
    db: AsyncSession, user_id: uuid.UUID
) -> UserPersonalization | None:
    """Get a user's personalization row."""
    result = await db.execute(
        select(UserPersonalization).where(UserPersonalization.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def upsert_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str | None,
    nickname: str | None,
    bio: str | None,
    content_niche: str | None,
    content_goal: str | None,
    content_intent: str | None,
    target_age_group: str | None,
    target_country: str | None,
    target_audience: str | None,
    usp: str | None,
) -> UserPersonalization:
    """
    Create or update a user's profile (upsert pattern).
    
    Why upsert? The first time a user saves, no profile exists (CREATE).
    Every time after, we UPDATE the existing profile. Upsert handles both
    cases in one function — cleaner than separate create/update endpoints.
    """
    profile = await get_profile_by_user_id(db, user_id)

    if profile:
        # Update existing
        if name is not None:
            profile.name = name
        profile.nickname = nickname
        profile.bio = bio
        profile.content_niche = content_niche
        profile.content_goal = content_goal
        profile.content_intent = content_intent
        profile.target_age_group = target_age_group
        profile.target_country = target_country
        profile.target_audience = target_audience
        profile.usp = usp
    else:
        # Create new
        profile = UserPersonalization(
            user_id=user_id,
            name=name or "",
            nickname=nickname,
            bio=bio,
            content_niche=content_niche,
            content_goal=content_goal,
            content_intent=content_intent,
            target_age_group=target_age_group,
            target_country=target_country,
            target_audience=target_audience,
            usp=usp,
        )
        db.add(profile) # queues the INSERT

    await db.commit() # sends INSERT to PostgreSQL
    await db.refresh(profile) # updates the Python object with the DB-generated ID
    return profile
