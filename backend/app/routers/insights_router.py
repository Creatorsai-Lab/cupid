"""
Insights Router — 5 endpoints for the analytics dashboard.

═══════════════════════════════════════════════════════════════════════════
ENDPOINTS
═══════════════════════════════════════════════════════════════════════════
GET /api/v1/insights/{connection_id}/summary
GET /api/v1/insights/{connection_id}/timeseries?range_days=30
GET /api/v1/insights/{connection_id}/top-content?limit=10
GET /api/v1/insights/{connection_id}/heatmap
GET /api/v1/insights/                                ← list connections + summaries

Why connection_id in path: a user could connect multiple platforms
in v2 (e.g. YouTube + Instagram). The frontend asks "show me insights
for connection X." Today there's only ever one, but the API stays
forward-compatible.

═══════════════════════════════════════════════════════════════════════════
AUTH PATTERN
═══════════════════════════════════════════════════════════════════════════
Every endpoint checks: does this connection BELONG to the current user?
If not, 404 (not 403 - we don't even acknowledge the connection exists).
This prevents user A from probing for user B's connection IDs.

404 vs 403 for unauthorized access. The auth gate returns 404 ("Connection not found") even when the connection exists but belongs to another user. This prevents enumeration attacks where an attacker probes for valid IDs. Real-world security pattern — Stripe, GitHub, basically everyone does this.
═══════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.insights import insights_service as insights_service
from app.models.social_connection import SocialConnection
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.insights_schema import (
    HeatmapResponse,
    SummaryResponse,
    TimeSeriesResponse,
    TopContentResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["insights"])


# ─── Helper: load + authorize connection ───────────────────────


async def _get_authorized_connection(
    connection_id: UUID,
    user: User,
    session: AsyncSession,
) -> SocialConnection:
    """
    Fetch a connection IFF it belongs to the current user.

    Used at the top of every endpoint as the auth gate.
    """
    stmt = (
        select(SocialConnection)
        .where(SocialConnection.id == connection_id)
        .where(SocialConnection.user_id == user.id)
    )
    connection = (await session.execute(stmt)).scalar_one_or_none()

    if connection is None:
        # 404 not 403: don't reveal whether the ID exists for some other user
        raise HTTPException(404, "Connection not found")

    return connection


# ─── List endpoint (no connection_id needed) ───────────────────


@router.get("/", response_model=list[SummaryResponse])
async def list_connections_with_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[SummaryResponse]:
    """
    Return summary for every connection the user has.

    Use case: dashboard "you have N connected platforms" overview.
    """
    stmt = select(SocialConnection).where(SocialConnection.user_id == current_user.id)
    connections = (await session.execute(stmt)).scalars().all()

    summaries = []
    for connection in connections:
        summary = await insights_service.get_summary(connection, session)
        summaries.append(summary)

    return summaries


# ─── Summary ───────────────────────────────────────────────────


@router.get("/{connection_id}/summary", response_model=SummaryResponse)
async def get_summary(
    connection_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SummaryResponse:
    """Stat cards for the dashboard top — subs, views, deltas."""
    connection = await _get_authorized_connection(connection_id, current_user, session)
    return await insights_service.get_summary(connection, session)


# ─── Time series ───────────────────────────────────────────────


@router.get("/{connection_id}/timeseries", response_model=TimeSeriesResponse)
async def get_timeseries(
    connection_id: UUID,
    range_days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TimeSeriesResponse:
    """Daily snapshots for line charts. Default 30 days, max 365."""
    connection = await _get_authorized_connection(connection_id, current_user, session)
    return await insights_service.get_timeseries(connection, session, range_days)


# ─── Top content ───────────────────────────────────────────────


@router.get("/{connection_id}/top-content", response_model=TopContentResponse)
async def get_top_content(
    connection_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TopContentResponse:
    """Top-N videos by views, sorted from #1 down."""
    connection = await _get_authorized_connection(connection_id, current_user, session)
    return await insights_service.get_top_content(connection, session, limit)


# ─── Heatmap ───────────────────────────────────────────────────


@router.get("/{connection_id}/heatmap", response_model=HeatmapResponse)
async def get_heatmap(
    connection_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> HeatmapResponse:
    """Day-of-week × hour grid of average views."""
    connection = await _get_authorized_connection(connection_id, current_user, session)
    return await insights_service.get_heatmap(connection, session)
