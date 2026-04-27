"""
Profile router — endpoints for reading and updating user persona data.

Endpoints:
    GET  /api/v1/profile  → get current user's profile
    PUT  /api/v1/profile  → create or update profile
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.persona import (
    PersonalizationApiResponse,
    PersonalizationResponse,
    PersonalizationUpdate,
)
from app.services.profile import get_profile_by_user_id, upsert_profile

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


@router.get("", response_model=PersonalizationApiResponse)
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's persona profile."""
    profile = await get_profile_by_user_id(db, user.id)
    if not profile:
        return PersonalizationApiResponse(data=None)
    return PersonalizationApiResponse(data=PersonalizationResponse.model_validate(profile))


@router.put("", response_model=PersonalizationApiResponse)
async def update_profile(
    body: PersonalizationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update the current user's persona profile."""
    profile = await upsert_profile(
        db=db,
        user_id=user.id,
        name=body.name,
        nickname=body.nickname,
        bio=body.bio,
        content_niche=body.content_niche,
        content_goal=body.content_goal,
        content_intent=body.content_intent,
        target_age_group=body.target_age_group,
        target_country=body.target_country,
        target_audience=body.target_audience,
        usp=body.usp,
    )
    return PersonalizationApiResponse(
        data=PersonalizationResponse.model_validate(profile)
    )
