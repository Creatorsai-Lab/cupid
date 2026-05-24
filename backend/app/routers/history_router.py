"""
History Router — endpoints for the creation history feature.

═══════════════════════════════════════════════════════════════════════════
ENDPOINTS
═══════════════════════════════════════════════════════════════════════════
GET    /api/v1/history/            list the user's creations (paginated)
DELETE /api/v1/history/{entry_id}  delete one entry

No "create" endpoint — entries are saved automatically by the pipeline
when a run completes (see history_service.save_creation).

Auth: every endpoint uses get_current_user. The user_id from the token
is the only user whose history can be read or modified — there's no way
to pass another user's ID.
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services import history_service 
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.history_schemas import HistoryEntry, HistoryListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/", response_model=HistoryListResponse)
async def list_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> HistoryListResponse:
    """Return the current user's creation history, newest first."""
    entries, total = await history_service.list_history(
        session, current_user.id, limit=limit, offset=offset,
    )

    return HistoryListResponse(
        entries=[HistoryEntry.model_validate(e, from_attributes=True) for e in entries],
        total=total,
        has_more=(offset + limit) < total,
    )


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_entry(
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Delete one history entry. 404 if it doesn't exist or isn't yours."""
    deleted = await history_service.delete_entry(
        session, current_user.id, entry_id,
    )
    if not deleted:
        raise HTTPException(404, "History entry not found")
    # 204 No Content — no return body