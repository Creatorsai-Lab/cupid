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
from app.schemas.profile import ProfileApiResponse, ProfileResponse, ProfileUpdate
from app.services.profile import get_profile_by_user_id, upsert_profile

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


@router.get("", response_model=ProfileApiResponse)
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's persona profile."""
    profile = await get_profile_by_user_id(db, user.id)
    if not profile:
        return ProfileApiResponse(data=None)
    return ProfileApiResponse(data=ProfileResponse.model_validate(profile))


@router.put("", response_model=ProfileApiResponse)
async def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update the current user's persona profile."""
    profile = await upsert_profile(
        db=db,
        user_id=user.id,
        bio=body.bio,
        field=body.field,
        skills=body.skills,
        geography=body.geography,
        audience=body.audience,
    )
    return ProfileApiResponse(data=ProfileResponse.model_validate(profile))
