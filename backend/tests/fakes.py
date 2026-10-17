"""Test doubles passed into the code under test (see tests.md, "Writing a test").

FakeLLM stands in for an LLMSession (app/agents/llm/gateway.py): same
structured() signature, queued answers, and a record of every call so tests
can check the prompts that were sent.

FakeRuns stands in for a RunStore (app/agents/runtime/runs.py) holding one run:
its status history, resume claims, and the execution lock.
"""

from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel


class FakeLLM:
    def __init__(self, *answers: Any) -> None:
        """Each answer is a model instance, a dict to validate, or an exception to raise."""
        self.answers = deque(answers)
        self.calls: list[dict[str, Any]] = []
        self.run_id = "fake-run"

    async def structured[M: BaseModel](
        self,
        system: str,
        user: str,
        response_model: type[M],
        *,
        role: str,
        temperature: float = 0.2,
    ) -> M:
        self.calls.append(
            {"system": system, "user": user, "schema": response_model, "role": role}
        )
        if not self.answers:
            raise AssertionError(f"FakeLLM has no answer left for role {role!r}")
        answer = self.answers.popleft()
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, response_model):
            return answer
        return response_model.model_validate(answer)

    def totals(self) -> dict[str, int | None]:
        return {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": None}


@dataclass
class FakeRuns:
    status: str = "queued"
    history: list[tuple[str, str | None]] = field(default_factory=list)
    claimable: bool = True  # False: another caller already claimed the resume
    claims: int = 0
    held_elsewhere: bool = False  # True: another worker is executing the run

    @property
    def statuses(self) -> list[str]:
        return [status for status, _ in self.history]

    @asynccontextmanager
    async def exclusive(self, run_id: str) -> AsyncIterator[bool]:
        yield not self.held_elsewhere

    async def get(self, run_id: str) -> SimpleNamespace:
        return SimpleNamespace(status=self.status)

    async def set_status(self, run_id: str, status: str, *, error: str | None = None):
        self.status = status
        self.history.append((status, error))

    async def claim_for_resume(self, run_id: str, user_id: Any) -> bool:
        self.claims += 1
        if self.claimable:
            self.status = "queued"
        return self.claimable
