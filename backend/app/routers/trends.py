"""
Trends Router — FastAPI endpoints exposed to the frontend.

Endpoints:
    GET /api/v1/trends/news     → personalized news feed
    POST /api/v1/trends/refresh → manually trigger ingestion (admin only later)

The router is intentionally thin. All real logic lives in service.py.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db                   
from app.core.redis import get_redis              # adjust to your Redis
from app.models.user import User
from app.routers.auth import get_current_user
from app.trends.schemas import TrendsResponse
from app.trends.service import get_trends_for_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("/news", response_model=TrendsResponse)
async def get_trending_news(
    refresh: bool = Query(False, description="Bypass cache and recompute"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TrendsResponse:
    """
    Returns the top 9 news articles personalized to the current user's niche.

    Implementation: pulls a pool of recent articles in the user's niche
    categories, ranks them with BM25 + recency + source authority, returns
    top 9. Cached per-user for 10 minutes.
    """
    persona = _extract_persona(current_user)

    try:
        response = await get_trends_for_user(
            user_id=str(current_user.id),
            persona=persona,
            session=session,
            redis=redis,
            bypass_cache=refresh,
        )
    except Exception as exc:
        logger.error("[trends.api] failed for user %s: %s", current_user.id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load trending news")

    return response


def _extract_persona(user: User) -> dict:
    """
    Build the persona dict the ranker expects from your User ORM object.

    Adjust this to match wherever your personalization data is stored.
    If it's on a separate Profile model, fetch that here.
    """
    return {
        "name":             getattr(user, "full_name", None),
        "content_niche":    getattr(user, "content_niche", None),
        "target_audience":  getattr(user, "target_audience", None),
        "target_country":   getattr(user, "target_country", None),
        "content_intent":   getattr(user, "content_intent", None),
        "usp":              getattr(user, "usp", None),
        "bio":              getattr(user, "bio", None),
    }