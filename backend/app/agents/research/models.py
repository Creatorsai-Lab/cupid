"""What the research step hands to the rest of the pipeline.

The research agent itself (Phase 3) keeps its own internal models; its adapter
turns a research result into this ResearchPack.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.agents.models import ContractModel


class Source(ContractModel):
    id: str = Field(min_length=1)  # "S1", "S2", … referenced by facts and pieces
    title: str
    url: str
    published_at: datetime | None = None


class SourceDocument(ContractModel):
    source_id: str
    content: str


class ResearchPack(ContractModel):
    status: Literal["complete", "low_coverage", "timeout", "failed", "skipped"]
    sources: tuple[Source, ...] = ()
    documents: tuple[SourceDocument, ...] = ()

    @model_validator(mode="after")
    def _unique_source_ids(self) -> "ResearchPack":
        ids = [s.id for s in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source ids must be unique")
        return self
