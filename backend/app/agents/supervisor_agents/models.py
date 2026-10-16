"""The supervisor's output: the plan every later step follows."""

from typing import Literal

from pydantic import model_validator

from app.agents.models import ContractModel


class RunPlan(ContractModel):
    """The supervisor's decision for this run (deterministic, no LLM call, D16)."""

    verdict: Literal["allow", "block"]
    reason: str | None = None  # shown to the user when blocked
    needs_research: bool = True
    deliverables: tuple[str, ...] = ()  # e.g. ("linkedin_post",)

    @model_validator(mode="after")
    def _consistent(self) -> "RunPlan":
        if self.verdict == "block" and not self.reason:
            raise ValueError("a blocked run must give a reason")
        if self.verdict == "allow" and not self.deliverables:
            raise ValueError("an allowed run must have at least one deliverable")
        return self
