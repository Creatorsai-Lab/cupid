"""What the research agent needs from outside. Cupid injects the real ones (an LLM
gateway session, Tavily search, the page extractor); tests inject fakes. The agent
never creates or closes them: whoever creates a provider closes it."""

from typing import Protocol

from pydantic import BaseModel

from app.agents.research_agents.models import (
    CandidatePage,
    ExtractedDocument,
    PlannedQuery,
    ResearchBrief,
)


class StructuredLLM(Protocol):
    async def structured[M: BaseModel](
        self,
        system: str,
        user: str,
        response_model: type[M],
        /,
        *,
        role: str,
        temperature: float = ...,
    ) -> M: ...


class SearchProvider(Protocol):
    async def search(
        self, query: PlannedQuery, brief: ResearchBrief, max_results: int, /
    ) -> list[CandidatePage]: ...


class PageFetcher(Protocol):
    async def extract(self, candidate: CandidatePage, /) -> ExtractedDocument: ...
