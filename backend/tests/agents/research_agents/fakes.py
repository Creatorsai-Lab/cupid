"""Deterministic async provider doubles for research-agent tests."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from typing import Any


class FakeLLM:
    """Queue structured responses while recording each request."""

    def __init__(self, *responses: Any) -> None:
        self.responses = deque(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    async def structured(
        self,
        system: str,
        user: str,
        response_model: type[Any],
        temperature: float = 0.2,
        role: str | None = None,
    ) -> Any:
        self.calls.append(
            {
                "system": system,
                "user": user,
                "response_model": response_model,
                "temperature": temperature,
                "role": role,
            }
        )
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return (
            response
            if isinstance(response, response_model)
            else response_model.model_validate(response)
        )

    @property
    def last_user_prompt(self) -> str:
        return self.calls[-1]["user"]

    async def close(self) -> None:
        self.closed = True


class FakeSearch:
    """Return query-ID keyed results or raise keyed exceptions."""

    def __init__(self, results_by_query: Mapping[str, Any] | None = None) -> None:
        self.results_by_query = dict(results_by_query or {})
        self.calls: list[Any] = []
        self.closed = False

    async def search(self, query: Any, brief: Any, max_results: int) -> list[Any]:
        self.calls.append(query)
        result: Any = self.results_by_query.get(query.id, [])
        if isinstance(result, BaseException):
            raise result
        if callable(result):
            result = result(query, brief, max_results)
        if hasattr(result, "__await__"):
            result = await result
        return list(result)

    async def close(self) -> None:
        self.closed = True


class FakeExtractor:
    """Return URL keyed extracted documents while recording calls."""

    def __init__(self, documents_by_url: Mapping[str, Any] | None = None) -> None:
        self.documents_by_url = dict(documents_by_url or {})
        self.calls: list[str] = []
        self.closed = False

    async def extract(self, candidate: Any) -> Any:
        self.calls.append(candidate.url)
        result = self.documents_by_url[candidate.url]
        if isinstance(result, Exception):
            raise result
        return result

    async def close(self) -> None:
        self.closed = True
