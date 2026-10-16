"""Which LLM serves which job. Switching a model is a change here, not in agents.

A role names a job in the pipeline ("writer", "judge", …) and lists the providers
that may serve it, in order of preference. The gateway uses the first available
one and keeps it for the whole run (plan D5).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from app.config import Settings

GROQ_URL = "https://api.groq.com/openai/v1"


@dataclass(frozen=True)
class ProviderSpec:
    """One model at one OpenAI-compatible endpoint."""

    name: str
    base_url: str
    model: str
    api_key: str = field(repr=False)
    strict_schema: bool = False  # supports response_format json_schema strict mode
    reasoning_effort: bool = False  # accepts the `reasoning_effort` field
    extra_body: Mapping[str, Any] = field(default_factory=dict)  # e.g. privacy options


@dataclass(frozen=True)
class RoleSpec:
    providers: tuple[str, ...]  # in order of preference
    timeout_s: float = 20.0
    # Sent only to providers that accept it, so failover never breaks a request.
    reasoning_effort: Literal["low", "medium", "high"] | None = None


# Groq meters quota per model, so the two models are separate providers.
# Reasoning effort: planning benefits from some deliberation; scoring does not
# (measured in the research agent: 650-1,250 hidden tokens per call at default).
ROLES: dict[str, RoleSpec] = {
    "research_planning": RoleSpec(("groq",), timeout_s=10.0, reasoning_effort="medium"),
    "research_evaluation": RoleSpec(("groq",), timeout_s=15.0, reasoning_effort="low"),
    "director": RoleSpec(("groq",), timeout_s=30.0),
    "writer": RoleSpec(("groq", "groq_fast"), timeout_s=30.0),
    "judge": RoleSpec(("groq_fast",), timeout_s=15.0, reasoning_effort="low"),
}


def configured_providers(settings: Settings) -> dict[str, ProviderSpec]:
    """Providers that have an API key; roles skip the rest."""
    providers: dict[str, ProviderSpec] = {}
    if settings.groq_api_key:
        for name, model in (
            ("groq", "openai/gpt-oss-120b"),
            ("groq_fast", "openai/gpt-oss-20b"),
        ):
            providers[name] = ProviderSpec(
                name,
                GROQ_URL,
                model,
                settings.groq_api_key,
                strict_schema=True,
                reasoning_effort=True,
            )
    return providers
