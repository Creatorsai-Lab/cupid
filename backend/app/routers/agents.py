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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.models.profile import UserPersonalization
from app.core.logging_config import get_agent_logger

logger = get_agent_logger("router")
router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


# In-memory run storage (V1 MVP — replace with Redis/PostgreSQL for production)
AGENT_RUNS: dict[str, dict] = {}

# Strong references to background tasks so they aren't GC'd mid-flight
_background_tasks: set[asyncio.Task] = set()


# ── Request / Response Schemas ────────────────────────────────

# Tones that directly map to a composition angle; everything else uses hook_first.
_TONE_TO_VOICE: dict[str, str] = {
    "Hook First":  "hook_first",
    "Data Driven": "data_driven",
    "Story Led":   "story_led",
}


class GenerateRequest(BaseModel):
    prompt: str
    content_type: Literal["Text", "Image", "Article", "Video", "Ads", "Poll"] = "Text"
    platform: Literal["Twitter", "LinkedIn", "Instagram", "Facebook", "YouTube", "Web"] = "Web"
    length: Literal["Short", "Medium", "Long", "Full Article"] = "Medium"
    tone: Literal[
        "Formal", "Informative", "Casual", "GenZ", "Factual",
        "Hook First", "Data Driven", "Story Led",
    ] = "Casual"


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
    composer_output: list | None = None
    composer_evidence: list | None = None
    composer_sources: list | None = None


# ── Background Pipeline ───────────────────────────────────────

async def run_agent_pipeline(
    run_id: str,
    user_id: str,
    request: GenerateRequest,
    personalization: dict[str, Any],
) -> None:
    """Sequential agent pipeline using orchestrator: Personalization → Research → Composer."""
    from app.agents.graph import get_orchestrator
    
    user_voice = _TONE_TO_VOICE.get(request.tone, "hook_first")
    
    logger.info("=" * 10, run_id)
    logger.info("🚀 PIPELINE START", run_id)
    logger.info("=" * 10, run_id)
    logger.info(f"  Run ID: {run_id}", run_id)
    logger.info(f"  User ID: {user_id}", run_id)
    logger.info(f"  Prompt: {request.prompt[:100]}{'...' if len(request.prompt) > 100 else ''}", run_id)
    logger.info(f"  Platform: {request.platform}", run_id)
    logger.info(f"  Tone: {request.tone} → Voice: {user_voice}", run_id)
    logger.info(f"  Length: {request.length}", run_id)
    logger.info("─" * 10, run_id)
    
    try:
        AGENT_RUNS[run_id]["status"] = "running"

        # Use the orchestrator to run the full pipeline
        logger.log_step(run_id, "Invoking orchestrator")
        orchestrator = get_orchestrator()
        final_state = await orchestrator.run(
            user_id=user_id,
            user_prompt=request.prompt,
            run_id=run_id,
            content_type=request.content_type,
            target_platform=request.platform,
            content_length=request.length,
            tone=request.tone,
            personalization=personalization,
        )

        # Update the run storage with final state
        AGENT_RUNS[run_id].update({
            "status": final_state.get("status", "completed"),
            "current_agent": final_state.get("current_agent"),
            "agents_completed": final_state.get("agents_completed", []),
            "personalization_queries": final_state.get("personalization_queries", []),
            "research_data": final_state.get("research_data"),
            "composer_output": final_state.get("composer_output", []),
            "composer_evidence": final_state.get("composer_evidence", []),
            "composer_sources": final_state.get("composer_sources", []),
            "error": final_state.get("error"),
        })

        logger.info("=" * 10, run_id)
        logger.info("✅ PIPELINE COMPLETE", run_id)
        logger.info(f"  Agents completed: {final_state.get('agents_completed', [])}", run_id)
        logger.info(f"  Status: {final_state.get('status', 'completed')}", run_id)
        logger.info("=" * 10, run_id)

    except Exception as exc:
        logger.error("=" * 10, run_id)
        logger.error("❌ PIPELINE FAILED", run_id, exc_info=True)
        logger.error(f"  Error: {str(exc)}", run_id)
        logger.error("=" * 10, run_id)
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

    user_voice = _TONE_TO_VOICE.get(request.tone, "hook_first")
    AGENT_RUNS[run_id] = {
        "run_id": run_id,
        "user_id": str(current_user.id),
        "created_at": datetime.now(timezone.utc),
        "user_prompt": request.prompt,
        "content_type": request.content_type,
        "target_platform": request.platform,
        "content_length": request.length,
        "tone": request.tone,
        "user_voice": user_voice,
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
        composer_evidence= state.get("composer_evidence", []),
        composer_sources= state.get("composer_sources", []),
    )
