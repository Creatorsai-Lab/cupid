"""Test doubles passed into the code under test (see tests.md, "Writing a test").

FakeLLM stands in for an LLMSession (app/agents/llm/gateway.py): same
structured() signature, queued answers, and a record of every call so tests
can check the prompts that were sent.
"""

from __future__ import annotations

from collections import deque
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

    def totals(self) -> dict[str, int]:
        return {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}
