"""
app/earn/router.py
═══════════════════════════════════════════════════════════════════════════

The Earn API. Thin by design — every endpoint validates, delegates to the
service, and shapes the response. No business logic lives here.

ENDPOINTS
─────────
  GET  /api/v1/earn/questions   → the Q&A set (renders the mandatory gate)
  GET  /api/v1/earn/profile     → has the gate been completed? (+ answers)
  POST /api/v1/earn/profile     → submit/replace Q&A answers (completeness enforced)
  GET  /api/v1/earn/readiness   → the full four-section page (REQUIRES a profile)

THE GATE, ENFORCED SERVER-SIDE
──────────────────────────────
"Mandatory Q&A" can't be a frontend-only rule. Two enforcement points:
  • POST /profile rejects incomplete or invalid answer maps (422).
  • GET /readiness returns 409 if no profile exists yet, so the page literally
    cannot render without the gate being completed — even if the client tried
    to skip it.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# Shared infrastructure (DB session + auth) — referenced, not modified.
from app.core.db import get_db
from app.models.user import User
from app.routers.auth import get_current_user

from app.earn import service
from app.earn.schemas import (
    EarnQuestionOut,
    ProfileResponse,
    ProfileSubmitRequest,
    QuestionOption,
    QuestionsResponse,
    ReadinessResponse,
)
from app.earn.streams import is_valid_answer_map, questions as _questions

router = APIRouter(prefix="/api/v1/earn", tags=["earn"])


# ─────────────────────────────────────────────────────────────────────────
#  Q&A questions — public-ish (auth still required, but no profile needed)
# ─────────────────────────────────────────────────────────────────────────

@router.get("/questions", response_model=QuestionsResponse)
async def get_questions(
    current_user: User = Depends(get_current_user),
) -> QuestionsResponse:
    """The Q&A set the frontend renders as the mandatory first-visit gate."""
    out = [
        EarnQuestionOut(
            stream_id=q.stream_id,
            question=q.question,
            options=[QuestionOption(value=v, label=l) for v, l in q.options],
        )
        for q in _questions()
    ]
    return QuestionsResponse(questions=out)


# ─────────────────────────────────────────────────────────────────────────
#  Profile (the gate state)
# ─────────────────────────────────────────────────────────────────────────

@router.get("/profile", response_model=ProfileResponse)
async def read_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileResponse:
    """exists=False → frontend shows the gate. exists=True → load the page."""
    return await service.get_profile(db, str(current_user.id))


@router.post("/profile", response_model=ProfileResponse)
async def submit_profile(
    payload: ProfileSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileResponse:
    """
    Submit/replace Q&A answers. Enforces a COMPLETE, VALID answer map server-
    side — 'mandatory' means we reject partial gates here, not just in the UI.
    """
    if not is_valid_answer_map(payload.answers):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Answers must cover every revenue stream with a valid option "
                   "(want / doing / no).",
        )
    return await service.save_profile(db, str(current_user.id), payload.answers)


# ─────────────────────────────────────────────────────────────────────────
#  Readiness (the page) — gated on a completed profile
# ─────────────────────────────────────────────────────────────────────────

@router.get("/readiness", response_model=ReadinessResponse)
async def get_readiness(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReadinessResponse:
    """
    The full four-section payload. 409 if the gate hasn't been completed —
    the page cannot be assembled without the creator's interest answers.
    """
    profile = await service.get_profile(db, str(current_user.id))
    if not profile.exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete the Earn questionnaire first.",
        )

    # The creator's niche comes from their persona. We read it defensively;
    # if it's unavailable the feature still works (universal matching only).
    raw_niche = await _resolve_niche(db, current_user)

    return await service.build_readiness_response(
        session=db,
        user_id=str(current_user.id),
        answers=profile.answers,
        raw_niche=raw_niche,
    )


async def _resolve_niche(db: AsyncSession, user: User) -> str | None:
    """
    Best-effort read of the creator's niche from their personalization profile.
    Isolated and defensive: any failure → None (universal matching), never a 500.
    """
    try:
        from sqlalchemy import select
        from app.models.persona import UserPersonalization

        result = await db.execute(
            select(UserPersonalization.content_niche).where(
                UserPersonalization.user_id == user.id
            )
        )
        return result.scalar_one_or_none()
    except Exception:  # noqa: BLE001
        return None