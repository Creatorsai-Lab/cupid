"""The one door to every LLM call: provider choice, failover and accounting.

    gateway = LLMGateway(configured_providers(settings))
    llm = gateway.session(run_id)          # one per run
    plan = await llm.structured(system, user, ResearchPlan, role="research_planning")

Rules (plan 5.5, built from the research agent's LLMClient):
- A run keeps the provider that last served each role (prompt caches stay warm,
  voice stays consistent); it moves on only when that provider fails.
- HTTP 429 puts a provider on cooldown for every run until Retry-After passes.
- Only connection failures are retried on the same provider (nothing was sent,
  nothing was spent). Anything after sending moves to the next provider and is
  never resent.
- An invalid answer is never resampled on the same provider: each try spends quota.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import re
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.agents.llm.errors import (
    NoProviderAvailableError,
    PermanentProviderError,
    ProviderCapacityError,
    ProviderError,
    RateLimitedError,
    RetryableProviderError,
    StructuredOutputError,
)
from app.agents.llm.roles import ROLES, ProviderSpec, RoleSpec

logger = logging.getLogger("app.agents.llm")

DEFAULT_COOLDOWN_S = 30.0
CONNECT_RETRY_DELAYS_S = (0.25, 0.75)


@dataclass(frozen=True)
class Usage:
    run_id: str
    role: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    latency_s: float


class LLMGateway:
    """Shared by all runs: owns the HTTP client and provider cooldowns."""

    def __init__(
        self,
        providers: Mapping[str, ProviderSpec],
        roles: Mapping[str, RoleSpec] = ROLES,
        *,
        http: httpx.AsyncClient | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        connect_retry_delays_s: Sequence[float] = CONNECT_RETRY_DELAYS_S,
    ) -> None:
        self._providers = dict(providers)
        self._roles = dict(roles)
        self._http = http or httpx.AsyncClient()
        self._clock = clock
        self._sleep = sleep
        self._retry_delays = tuple(connect_retry_delays_s)
        self._cooldown_until: dict[str, float] = {}

    def session(self, run_id: str) -> LLMSession:
        return LLMSession(self, run_id)

    async def close(self) -> None:
        await self._http.aclose()

    # ── Provider selection ──

    def candidates(self, role: str, preferred: str | None) -> list[ProviderSpec]:
        """Configured providers for the role that aren't cooling down, run's choice first."""
        spec = self._roles.get(role)
        if spec is None:
            raise NoProviderAvailableError(f"unknown role {role!r}")
        now = self._clock()
        ready = [
            self._providers[name]
            for name in spec.providers
            if name in self._providers and self._cooldown_until.get(name, 0.0) <= now
        ]
        ready.sort(key=lambda p: p.name != preferred)  # stable: keeps preference order
        return ready

    def _cool_down(self, provider: ProviderSpec, response: httpx.Response) -> None:
        try:
            seconds = float(response.headers.get("Retry-After", DEFAULT_COOLDOWN_S))
        except ValueError:
            seconds = DEFAULT_COOLDOWN_S
        self._cooldown_until[provider.name] = self._clock() + seconds

    # ── One call to one provider ──

    async def complete_json(
        self,
        provider: ProviderSpec,
        role: str,
        system: str,
        user: str,
        schema: type[BaseModel],
        temperature: float,
    ) -> tuple[str, dict[str, Any]]:
        """Send one request; return (answer text, usage). Raises ProviderError."""
        spec = self._roles[role]
        body = _request_body(provider, spec, system, user, schema, temperature)
        response = await self._post(provider, body, spec.timeout_s)
        return _parse_response(provider, response, self._cool_down)

    async def _post(
        self, provider: ProviderSpec, body: dict[str, Any], timeout_s: float
    ) -> httpx.Response:
        attempts = len(self._retry_delays) + 1
        for attempt in range(attempts):
            try:
                return await self._http.post(
                    f"{provider.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {provider.api_key}"},
                    json=body,
                    timeout=timeout_s,
                )
            except (
                httpx.ConnectError,
                httpx.ConnectTimeout,
                httpx.PoolTimeout,
            ) as error:
                # Never reached the model: retrying costs nothing.
                if attempt + 1 == attempts:
                    raise RetryableProviderError(
                        f"{provider.name}: connection failed"
                    ) from error
                await self._sleep(self._retry_delays[attempt])
            except httpx.TransportError as error:
                # May have reached the model and spent tokens: never resend.
                raise RetryableProviderError(
                    f"{provider.name}: {type(error).__name__}"
                ) from error
        raise RetryableProviderError(
            f"{provider.name}: connection failed"
        )  # loop returns or raises


class LLMSession:
    """One run's view of the gateway: sticky provider per role and usage totals."""

    def __init__(self, gateway: LLMGateway, run_id: str) -> None:
        self._gateway = gateway
        self.run_id = run_id
        self._chosen: dict[str, str] = {}
        self.usage: list[Usage] = []

    async def structured[M: BaseModel](
        self,
        system: str,
        user: str,
        response_model: type[M],
        *,
        role: str,
        temperature: float = 0.2,
    ) -> M:
        """One schema-validated answer, walking the role's providers on failure."""
        providers = self._gateway.candidates(role, self._chosen.get(role))
        if not providers:
            raise NoProviderAvailableError(f"no provider available for role {role!r}")

        last_error: ProviderError | None = None
        for provider in providers:
            started = time.perf_counter()
            try:
                text, usage = await self._gateway.complete_json(
                    provider, role, system, user, response_model, temperature
                )
                result = _validate(text, response_model, provider)
            except ProviderError as error:
                logger.warning(
                    "llm run=%s role=%s provider=%s failed: %s",
                    self.run_id,
                    role,
                    provider.name,
                    error,
                )
                last_error = error
                continue
            self._chosen[role] = provider.name
            self._record(role, provider, usage, time.perf_counter() - started)
            return result
        raise last_error or NoProviderAvailableError(f"no provider served {role!r}")

    def totals(self) -> dict[str, int]:
        return {
            "prompt_tokens": sum(u.prompt_tokens for u in self.usage),
            "completion_tokens": sum(u.completion_tokens for u in self.usage),
            "cached_tokens": sum(u.cached_tokens for u in self.usage),
        }

    def _record(
        self, role: str, provider: ProviderSpec, raw: dict[str, Any], latency_s: float
    ) -> None:
        details = raw.get("prompt_tokens_details") or {}
        usage = Usage(
            run_id=self.run_id,
            role=role,
            provider=provider.name,
            model=provider.model,
            prompt_tokens=int(raw.get("prompt_tokens") or 0),
            completion_tokens=int(raw.get("completion_tokens") or 0),
            cached_tokens=int(details.get("cached_tokens") or 0),
            latency_s=latency_s,
        )
        self.usage.append(usage)
        logger.info(
            "llm run=%s role=%s provider=%s model=%s in=%d cached=%d out=%d %.2fs",
            usage.run_id,
            usage.role,
            usage.provider,
            usage.model,
            usage.prompt_tokens,
            usage.cached_tokens,
            usage.completion_tokens,
            usage.latency_s,
        )


# ── Helpers ────────────────────────────────────────────────────


def _request_body(
    provider: ProviderSpec,
    role: RoleSpec,
    system: str,
    user: str,
    schema: type[BaseModel],
    temperature: float,
) -> dict[str, Any]:
    """A fresh body per request, so one provider's fields never leak into another's."""
    if provider.strict_schema:
        response_format: dict[str, Any] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "strict": True,
                "schema": _strict_schema(schema.model_json_schema()),
            },
        }
    else:
        response_format = {"type": "json_object"}
    body: dict[str, Any] = {
        "model": provider.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "response_format": response_format,
        **copy.deepcopy(dict(provider.extra_body)),
    }
    if role.reasoning_effort and provider.reasoning_effort:
        body["reasoning_effort"] = role.reasoning_effort
    return body


def _parse_response(
    provider: ProviderSpec,
    response: httpx.Response,
    cool_down: Callable[[ProviderSpec, httpx.Response], None],
) -> tuple[str, dict[str, Any]]:
    status = response.status_code
    if status == 429:
        cool_down(provider, response)
        raise RateLimitedError(f"{provider.name}: HTTP 429")
    if status == 413:
        raise ProviderCapacityError(f"{provider.name}: HTTP 413 (request too large)")
    if status >= 500:
        raise RetryableProviderError(f"{provider.name}: HTTP {status}")
    if status >= 400:
        raise PermanentProviderError(
            f"{provider.name}: HTTP {status}: {_error_detail(response)}"
        )
    try:
        payload = response.json()
        text = payload["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise RetryableProviderError(f"{provider.name}: unusable response") from error
    if not isinstance(text, str):
        raise RetryableProviderError(f"{provider.name}: non-text answer")
    return text, payload.get("usage") or {}


def _validate[M: BaseModel](text: str, schema: type[M], provider: ProviderSpec) -> M:
    """Parse JSON (bare or in a ``` fence) and validate it against the schema."""
    stripped = text.strip()
    fenced = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```", stripped, re.IGNORECASE | re.DOTALL
    )
    try:
        return schema.model_validate(
            json.loads(fenced.group(1) if fenced else stripped)
        )
    except (json.JSONDecodeError, ValidationError) as error:
        raise StructuredOutputError(
            f"{provider.name}: answer is not a valid {schema.__name__}"
        ) from error


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Strict mode needs every object closed and every property required (copy, not mutate)."""
    strict = copy.deepcopy(schema)

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if node.get("type") == "object" or isinstance(properties, dict):
                node["additionalProperties"] = False
                if isinstance(properties, dict):
                    node["required"] = list(properties)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(strict)
    return strict


def _error_detail(response: httpx.Response) -> str:
    """A short, single-line description of a provider error body."""
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict):
            body = " ".join(
                str(error[k]) for k in ("code", "type", "message") if error.get(k)
            )
        else:
            body = error
    return re.sub(r"\s+", " ", str(body))[:200]
