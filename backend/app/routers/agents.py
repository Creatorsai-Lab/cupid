"""
Agent API Router - Endpoints for triggering and monitoring agent runs.

Endpoints:
- POST /api/v1/agents/generate → Trigger agent pipeline (async)
- GET /api/v1/agents/runs/{run_id} → Poll run status and results

Pipeline order:
    1. Personalization Agent — generates 5 search queries via Gemini
    2. Research Agent       — runs web search + extraction on those queries
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, cast

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.models.profile import UserPersonalization
from app.agents.state import MemoryState
from app.agents.personalization.agent import personalization_node
from app.agents.research.agent import research_node

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


# In-memory run storage (V1 MVP — replace with Redis/PostgreSQL for production)
AGENT_RUNS: dict[str, dict] = {}

# Strong references to background tasks so they aren't GC'd mid-flight
_background_tasks: set[asyncio.Task] = set()


# ── Request / Response Schemas ────────────────────────────────

class GenerateRequest(BaseModel):
    prompt: str
    content_type: Literal["Text", "Image", "Article", "Video", "Ads", "Poll"] = "Text"
    platform: Literal["All", "Twitter", "LinkedIn", "Instagram", "Facebook", "YouTube"] = "All"
    length: Literal["Short", "Medium", "Long"] = "Medium"
    tone: Literal["Formal", "Informative", "Casual", "GenZ"] = "Casual"


class GenerateResponse(BaseModel):
    run_id: str
    status: str
    message: str


class RunStatusResponse(BaseModel):
    run_id: str
    status: Literal["pending", "running", "completed", "failed"]
    created_at: datetime
    current_agent: str | None = None
    agents_completed: list[str] = []
    error: str | None = None
    personalization_queries: list[str] = []
    research_data: dict | None = None
    trend_data: dict | None = None
    composer_output: dict | None = None


# ── Background Pipeline ───────────────────────────────────────

async def run_agent_pipeline(
    run_id: str,
    user_id: str,
    request: GenerateRequest,
    personalization: dict[str, Any],
) -> None:
    """
    Sequential agent pipeline:
        1. personalization_node  →  writes personalization_queries to state
        2. research_node         →  reads queries, runs search + extraction
    """
    try:
        logger.info("[Pipeline] Starting run %s — prompt: %r", run_id, request.prompt[:60])
        AGENT_RUNS[run_id]["status"] = "running"

        # ── Initial state ─────────────────────────────────────
        state: MemoryState = cast(
            MemoryState,
            {
                "run_id": run_id,
                "user_id": user_id,
                "user_prompt": request.prompt,
                "content_type": request.content_type,
                "target_platform": request.platform,
                "content_length": request.length,
                "tone": request.tone,
                "personalization": personalization,
                "personalization_queries": [],
                "agents_completed": [],
                "status": "running",
            },
        )

        # ── Step 1: Personalization Agent ─────────────────────
        logger.info("[Pipeline] Running personalization agent…")
        AGENT_RUNS[run_id]["current_agent"] = "personalization"

        p_result = await personalization_node(state)
        AGENT_RUNS[run_id].update(p_result)

        # Merge output into state so Research Agent sees the queries
        state = cast(MemoryState, {**state, **p_result})

        logger.info(
            "[Pipeline] Personalization done — %d queries generated",
            len(p_result.get("personalization_queries", [])),
        )

        # ── Step 2: Research Agent ────────────────────────────
        logger.info("[Pipeline] Running research agent…")
        AGENT_RUNS[run_id]["current_agent"] = "research"

        r_result = await research_node(state)
        AGENT_RUNS[run_id].update(r_result)

        rd = r_result.get("research_data") or {}
        logger.info(
            "[Pipeline] Research done — sources: %d | pages: %d",
            len(rd.get("top_search_results", [])),
            len(rd.get("fetched_pages", [])),
        )

        # Mark completed (unless an agent already set status to "failed")
        if AGENT_RUNS[run_id].get("status") != "failed":
            AGENT_RUNS[run_id]["status"] = "completed"

    except Exception as exc:
        logger.error("[Pipeline] FAILED run %s: %s", run_id, exc, exc_info=True)
        AGENT_RUNS[run_id]["status"] = "failed"
        AGENT_RUNS[run_id]["error"] = str(exc)


# ── API Endpoints ─────────────────────────────────────────────

@router.post("/generate", response_model=GenerateResponse)
async def generate_content(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger the agent pipeline to generate content.

    Returns a run_id immediately. Poll GET /agents/runs/{run_id} for results.
    """
    from sqlalchemy import select

    stmt = select(UserPersonalization).where(
        UserPersonalization.user_id == current_user.id
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    personalization = {
        "name": (profile.name if profile else current_user.full_name) or "",
        "nickname": profile.nickname if profile else None,
        "bio": profile.bio if profile else None,
        "content_niche": profile.content_niche if profile else None,
        "content_goal": profile.content_goal if profile else None,
        "content_intent": profile.content_intent if profile else None,
        "target_age_group": profile.target_age_group if profile else None,
        "target_country": profile.target_country if profile else None,
        "target_audience": profile.target_audience if profile else None,
        "usp": profile.usp if profile else None,
    }

    run_id = str(uuid.uuid4())

    AGENT_RUNS[run_id] = {
        "run_id": run_id,
        "user_id": str(current_user.id),
        "created_at": datetime.now(timezone.utc),
        "user_prompt": request.prompt,
        "content_type": request.content_type,
        "target_platform": request.platform,
        "content_length": request.length,
        "tone": request.tone,
        "personalization": personalization,
        "personalization_queries": [],
        "agents_completed": [],
        "current_agent": None,
        "status": "pending",
        "error": None,
    }

    task = asyncio.create_task(
        run_agent_pipeline(
            run_id=run_id,
            user_id=str(current_user.id),
            request=request,
            personalization=personalization,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return GenerateResponse(
        run_id=run_id,
        status="pending",
        message="Agent pipeline started. Poll /agents/runs/{run_id} for results.",
    )


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
async def get_run_status(
    run_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get the status and results of an agent run."""
    if run_id not in AGENT_RUNS:
        raise HTTPException(status_code=404, detail="Run not found")

    state = AGENT_RUNS[run_id]

    if state.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    return RunStatusResponse(
        run_id=run_id,
        status=state.get("status", "pending"),
        created_at=state.get("created_at", datetime.now(timezone.utc)),
        current_agent=state.get("current_agent"),
        agents_completed=state.get("agents_completed", []),
        error=state.get("error"),
        personalization_queries=state.get("personalization_queries", []),
        research_data=state.get("research_data"),
        trend_data=state.get("trend_data"),
        composer_output=state.get("composer_output"),
    )
