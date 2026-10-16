"""Research step. Writes `research`.

Placeholder until Phase 3, when the research agent from
D:\\cupid_agents\\web-search-agent is ported here: it does no research and says so.
"""

from typing import Any

from app.agents.research_agents.models import ResearchPack
from app.agents.state import RunState


async def research(state: RunState) -> dict[str, Any]:
    return {"research": ResearchPack(status="skipped")}
