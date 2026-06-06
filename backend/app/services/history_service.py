"""
History Service — save completed creations and query them back.

═══════════════════════════════════════════════════════════════════════════
TWO RESPONSIBILITIES
═══════════════════════════════════════════════════════════════════════════
save_creation()  — called at the end of the pipeline when a run completes
list_history()   — called by the history page to render the feed
delete_entry()   — called when the user deletes one card

Keeping these in a service (not inline in the router) means the save logic
can be called from anywhere the pipeline finishes — whether that's the
agents router, a Celery task, or a future webhook.
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import update as sa_update
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.creation_history import CreationHistory

logger = logging.getLogger(__name__)


async def save_creation(
    session: AsyncSession,
    user_id: UUID,
    prompt: str,
    variants: list[dict],
    target_platform: str = "All",
    tone: str | None = None,
) -> CreationHistory | None:
    """
    Persist a completed creation to history.

    Returns the saved row, or None if there were no variants to save
    (we don't save empty/failed runs — history should only contain
    successful generations the user can actually reuse).

    Defensive: this is called from the pipeline's completion path, so it
    must NEVER raise in a way that breaks the user's response. If saving
    fails, we log and return None — the user still got their content.
    """
    if not variants:
        logger.info("[history] skipping save — no variants in completed run")
        return None

    # Trim variants to only the fields we display. Drops quality scores,
    # hashtags, and any other intermediate fields the history view ignores.
    slim_variants = [
        {
            "angle":      v.get("angle", ""),
            "platform":   v.get("platform", target_platform),
            "content":    v.get("content", ""),
            "char_count": v.get("char_count", len(v.get("content", ""))),
        }
        for v in variants
        if v.get("content")
    ]

    if not slim_variants:
        return None

    try:
        entry = CreationHistory(
            user_id=user_id,
            prompt=prompt.strip(),
            target_platform=target_platform,
            tone=tone,
            variants=slim_variants,
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        logger.info(
            "[history] saved creation %s for user %s (%d variants)",
            entry.id, user_id, len(slim_variants),
        )
        return entry
    except Exception as exc:
        # Never let a history-save failure break the user's flow
        await session.rollback()
        logger.warning("[history] save failed for user %s: %s", user_id, exc)
        return None


async def list_history(
    session: AsyncSession,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[CreationHistory], int]:
    """
    Return (entries, total_count) for a user, newest first.

    Pagination via limit/offset. The total count lets the frontend show
    "showing 20 of 64" and decide whether to render a "load more" button.
    """
    # Total count for pagination metadata
    count_stmt = (
        select(func.count())
        .select_from(CreationHistory)
        .where(CreationHistory.user_id == user_id)
    )
    total = (await session.execute(count_stmt)).scalar() or 0

    # The page of entries
    stmt = (
        select(CreationHistory)
        .where(CreationHistory.user_id == user_id)
        .order_by(CreationHistory.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    entries = list((await session.execute(stmt)).scalars().all())

    return entries, total


async def update_variants(
    session: AsyncSession,
    user_id: UUID,
    entry_id: UUID,
    variants: list[dict],
) -> bool:
    """
    Replace the variants of one history entry IF it belongs to the user.

    Used when the user edits a generated post after the fact. Returns True if
    a row was updated, False if not found / not owned. The user_id in the WHERE
    clause is the authorization gate.
    """
    slim_variants = [
        {
            "angle":      v.get("angle", ""),
            "platform":   v.get("platform", ""),
            "content":    v.get("content", ""),
            "char_count": v.get("char_count", len(v.get("content", ""))),
        }
        for v in variants
        if v.get("content")
    ]
    if not slim_variants:
        return False

    stmt = (
        sa_update(CreationHistory)
        .where(CreationHistory.id == entry_id)
        .where(CreationHistory.user_id == user_id)
        .values(variants=slim_variants)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0


async def delete_entry(
    session: AsyncSession,
    user_id: UUID,
    entry_id: UUID,
) -> bool:
    """
    Delete one history entry IF it belongs to the user.

    Returns True if a row was deleted, False if not found / not owned.
    The user_id check in the WHERE clause is the authorization gate —
    a user can only delete their own entries.
    """
    stmt = (
        sa_delete(CreationHistory)
        .where(CreationHistory.id == entry_id)
        .where(CreationHistory.user_id == user_id)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0