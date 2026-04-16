"""
Agent API Router - Endpoints for triggering and monitoring agent runs.

Endpoints:
- POST /api/v1/agents/generate → Trigger agent pipeline (async)
- GET /api/v1/agents/runs/{run_id} → Poll run status and results
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
from app.agents.research.agent import research_node

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


# In-memory storage for agent runs (V1 MVP)
# In production, this should be Redis or PostgreSQL
AGENT_RUNS: dict[str, dict] = {}

# Strong references to background tasks so they aren't garbage-collected
_background_tasks: set[asyncio.Task] = set()


# ── Request/Response Schemas ─────────────────────────────────

class GenerateRequest(BaseModel):
    """Request body for POST /agents/generate"""
    prompt: str
    content_type: Literal["Text", "Image", "Article", "Video", "Ads", "Poll"] = "Text"
    platform: Literal["All", "Twitter", "LinkedIn", "Instagram", "Facebook", "YouTube"] = "All"
    length: Literal["Short", "Medium", "Long"] = "Medium"
    tone: Literal["Formal", "Informative", "Casual", "GenZ"] = "Casual"


class GenerateResponse(BaseModel):
    """Response for POST /agents/generate"""
    run_id: str
    status: str
    message: str


class RunStatusResponse(BaseModel):
    """Response for GET /agents/runs/{run_id}"""
    run_id: str
    status: Literal["pending", "running", "completed", "failed"]
    created_at: datetime
    current_agent: str | None = None
    agents_completed: list[str] = []
    error: str | None = None
    research_data: dict | None = None
    trend_data: dict | None = None
    composer_output: dict | None = None


# ── Background Task Functions ────────────────────────────────

async def run_agent_pipeline(
    run_id: str,
    user_id: str,
    request: GenerateRequest,
    personalization: dict[str, Any],
) -> None:
    """
    Background task that executes the agent pipeline.

    V1: Calls research_node directly (no LangGraph overhead for a
    single-agent flow). When V2 adds more agents, swap this back
    to the LangGraph orchestrator.
    """
    try:
        logger.info(f"[Pipeline] Starting run {run_id} — prompt: {request.prompt[:60]!r}")
        AGENT_RUNS[run_id]["status"] = "running"

        # Build the state dict that research_node expects
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
            "agents_completed": [],
            "status": "running",
            },
        )

        # Call research agent directly — no LangGraph indirection for V1
        result = await research_node(state)

        # Merge the agent's output into the stored run state
        AGENT_RUNS[run_id].update(result)

        # Only mark completed if the agent didn't set status to "failed"
        if AGENT_RUNS[run_id].get("status") != "failed":
            AGENT_RUNS[run_id]["status"] = "completed"

        rd = result.get("research_data") or {}
        logger.info(
            f"[Pipeline] Completed run {run_id} — "
            f"sources: {len(rd.get('top_search_results', []))} | "
            f"pages: {len(rd.get('fetched_pages', []))}"
        )

    except Exception as e:
        logger.error(f"[Pipeline] FAILED run {run_id}: {e}", exc_info=True)
        AGENT_RUNS[run_id]["status"] = "failed"
        AGENT_RUNS[run_id]["error"] = str(e)


# ── API Endpoints ────────────────────────────────────────────

@router.post("/generate", response_model=GenerateResponse)
async def generate_content(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger the agent pipeline to generate content.

    Flow:
    1. Validate user is authenticated
    2. Fetch user profile for personalization
    3. Create run_id and initialize state
    4. Trigger background task
    5. Return run_id immediately

    The client should poll GET /agents/runs/{run_id} for results.
    """
    # Fetch user profile
    from sqlalchemy import select

    stmt = select(UserPersonalization).where(
        UserPersonalization.user_id == current_user.id
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    # Build personalization payload (matches Settings `PersonalizationForm`)
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

    # Create run
    run_id = str(uuid.uuid4())

    # Initialize state
    initial_state: dict[str, Any] = {
        "run_id": run_id,
        "user_id": str(current_user.id),
        "created_at": datetime.now(timezone.utc),
        "user_prompt": request.prompt,
        "content_type": request.content_type,
        "target_platform": request.platform,
        "content_length": request.length,
        "tone": request.tone,
        "personalization": personalization,
        "agents_completed": [],
        "status": "pending",
        "error": None,
    }

    AGENT_RUNS[run_id] = initial_state  # type: ignore

    # Launch as an async task with a stored reference to prevent GC
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
    """
    Get the status and results of an agent run.

    Returns:
    - Status (pending/running/completed/failed)
    - Completed agents
    - Research data (if completed)
    - Error message (if failed)
    """
    # Check if run exists
    if run_id not in AGENT_RUNS:
        raise HTTPException(status_code=404, detail="Run not found")

    state = AGENT_RUNS[run_id]

    # Verify user owns this run
    if state.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Build response
    return RunStatusResponse(
        run_id=run_id,
        status=state.get("status", "pending"),
        created_at=state.get("created_at", datetime.now(timezone.utc)),
        current_agent=state.get("current_agent"),
        agents_completed=state.get("agents_completed", []),
        error=state.get("error"),
        research_data=state.get("research_data"),
        trend_data=state.get("trend_data"),
        composer_output=state.get("composer_output"),
    )
