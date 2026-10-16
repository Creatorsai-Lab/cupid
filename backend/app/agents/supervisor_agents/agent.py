"""Supervisor step: the first step of every run. Writes `plan`.

Placeholder until Phase 4 (deterministic rules, plan limits, deliverables
table): it blocks an empty prompt and plans one post for the chosen platform.
"""

from typing import Any

from app.agents.state import RunState
from app.agents.supervisor_agents.models import RunPlan


async def supervise(state: RunState) -> dict[str, Any]:
    request = state["request"]
    if not request.prompt.strip():
        plan = RunPlan(
            verdict="block", reason="Please describe what you want to create."
        )
    else:
        plan = RunPlan(
            verdict="allow", deliverables=(f"{request.platform.lower()}_post",)
        )
    return {"plan": plan}
