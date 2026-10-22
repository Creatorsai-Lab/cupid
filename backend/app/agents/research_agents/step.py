"""Research step: the pipeline's research node. Writes `research`.

Cupid's wiring around the research agent (agent.py): reads the run state, runs
the agent, returns a ResearchPack. Placeholder until the agent is integrated:
it does no research and says so.
"""

from typing import Any, Protocol

from app.agents.research_agents.adapter import degradation_issues, persona_for, to_pack
from app.agents.research_agents.agent import ResearchAgent
from app.agents.research_agents.config import CONFIG, Config
from app.agents.research_agents.interfaces import (
    PageFetcher,
    SearchProvider,
    StructuredLLM,
)
from app.agents.research_agents.models import ResearchPack
from app.agents.state import RunState


async def research(state: RunState) -> dict[str, Any]:
    return {"research": ResearchPack(status="skipped")}


class LLMSessions(Protocol):
    """Anything that hands out one LLM session per run (Cupid's LLMGateway)."""

    def session(self, run_id: str) -> StructuredLLM: ...


class ResearchStep:
    """Created once per worker; each call is one run's research."""

    def __init__(
        self,
        llm: LLMSessions,
        search: SearchProvider,
        extractor: PageFetcher,
        config: Config = CONFIG,
    ) -> None:
        self._llm = llm
        self._search = search
        self._extractor = extractor
        self._config = config

    async def __call__(self, state: RunState) -> dict[str, Any]:
        request = state["request"]
        agent = ResearchAgent(
            self._config,
            llm=self._llm.session(request.run_id),
            search=self._search,
            extractor=self._extractor,
        )
        result = await agent.run(
            request.prompt, persona_for(request, state.get("profile"))
        )
        # to_pack raises StepFailedError when research failed (retried, then shown).
        update: dict[str, Any] = {"research": to_pack(result)}
        if issues := degradation_issues(result):
            update["issues"] = issues
        return update
