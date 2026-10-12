"""The run pool: the shared state every pipeline step reads and writes.

Three zones (plan 5.1):
- inputs, written once at the start of the run;
- shared decisions, each written by exactly one owning step;
- outputs, written by steps in parallel and merged by reducers.

check_update() enforces ownership: a step that writes a field it doesn't own
fails immediately instead of silently corrupting the run.

Phase 5 adds `voice` (input) and `brief` (owned by the studio director).
"""

import operator
from typing import Annotated, Any, TypedDict

from app.agents.models import CreatorProfile, Issue, RunPlan, RunRequest
from app.agents.research.models import ResearchPack
from app.agents.studio.models import ContentPiece

START = "start"  # the runtime, when it creates the run
ANY_STEP = "*"


class RunState(TypedDict, total=False):
    # Inputs
    request: RunRequest
    profile: CreatorProfile
    # Shared decisions
    plan: RunPlan
    research: ResearchPack
    # Outputs (parallel writers, merged)
    pieces: Annotated[list[ContentPiece], operator.add]
    issues: Annotated[list[Issue], operator.add]


OWNERS: dict[str, str] = {
    "request": START,
    "profile": START,
    "plan": "supervisor",
    "research": "research",
    "pieces": "studio",
    "issues": ANY_STEP,
}


def check_update(step: str, update: dict[str, Any]) -> dict[str, Any]:
    """Return `update` unchanged if `step` owns every field in it; raise otherwise."""
    for field in update:
        owner = OWNERS.get(field)
        if owner is None:
            raise PermissionError(f"unknown state field {field!r} written by {step}")
        if owner not in (step, ANY_STEP):
            raise PermissionError(f"{step} may not write {field!r} (owned by {owner})")
    return update
