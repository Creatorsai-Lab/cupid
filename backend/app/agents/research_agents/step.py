"""Research step: the pipeline's research node. Writes `research`.

Cupid's wiring around the research agent (agent.py): reads the run state, runs
the agent, returns a ResearchPack. Placeholder until the agent is integrated:
it does no research and says so.
"""

from typing import Any

from app.agents.research_agents.models import ResearchPack
from app.agents.state import RunState


async def research(state: RunState) -> dict[str, Any]:
    return {"research": ResearchPack(status="skipped")}
