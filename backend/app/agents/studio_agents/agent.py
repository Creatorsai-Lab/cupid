"""Studio step. Writes `pieces`.

Placeholder until Phase 5 (director, specialists, reviewer): one clearly
labeled draft per planned deliverable, so the pipeline runs end to end.
"""

from typing import Any

from app.agents.state import RunState
from app.agents.studio_agents.models import ContentPiece, TextBlock


async def create(state: RunState) -> dict[str, Any]:
    request, plan = state["request"], state.get("plan")
    if plan is None:
        raise RuntimeError("studio ran before the supervisor planned the run")
    pieces = [
        ContentPiece(
            id=f"{request.run_id}-{deliverable}-1",
            deliverable=deliverable,
            variant=1,
            blocks=(
                TextBlock(role="body", text=f"[Placeholder draft] {request.prompt}"),
            ),
        )
        for deliverable in plan.deliverables
    ]
    return {"pieces": pieces}
