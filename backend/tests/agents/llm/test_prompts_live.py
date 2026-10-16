"""Prompt caching works end to end: two calls sharing a long system prompt, the
second reports cached tokens. Run: uv run pytest -m integration"""

import pytest
from pydantic import BaseModel

from app.agents.llm.gateway import LLMGateway
from app.agents.llm.prompts import build_prompt
from app.agents.llm.roles import ROLES, configured_providers
from app.config import settings

pytestmark = pytest.mark.integration

# ~2,000 tokens of shared context: above Groq's minimum cacheable prefix.
FACTS = [
    f"Fact {i}: creators who post weekly grow {i % 7 + 2}x faster [S{i}]"
    for i in range(150)
]


class Choice(BaseModel):
    fact_number: int


@pytest.mark.skipif(not settings.groq_api_key, reason="GROQ_API_KEY not set")
async def test_shared_prefix_is_served_from_cache():
    gateway = LLMGateway(configured_providers(settings), ROLES)
    session = gateway.session("cache-check")
    try:
        for n in (3, 4):
            prompt = build_prompt(
                instructions="Pick the requested fact number from the run context.",
                context={"facts": FACTS},
                task=f"Return fact_number {n}.",
            )
            await session.structured(prompt.system, prompt.user, Choice, role="judge")
    finally:
        await gateway.close()

    first, second = session.usage
    print(f"\nfirst: in={first.prompt_tokens} cached={first.cached_tokens}")
    print(f"second: in={second.prompt_tokens} cached={second.cached_tokens}")
    if second.cached_tokens is None:
        # Seen on Groq's free tier (2026-10-16): responses carry no cache data.
        pytest.skip(
            f"{second.provider} does not report prompt caching for this account"
        )
    assert second.cached_tokens > 0
