"""One real call per configured provider: proves the live API still matches what the
gateway expects (strict schema, usage fields). Run: uv run pytest -m integration"""

import pytest
from pydantic import BaseModel

from app.agents.llm.gateway import LLMGateway
from app.agents.llm.roles import ROLES, configured_providers
from app.config import settings

pytestmark = pytest.mark.integration


class Capital(BaseModel):
    country: str
    capital: str


@pytest.mark.skipif(not settings.groq_api_key, reason="GROQ_API_KEY not set")
@pytest.mark.parametrize("role", ["research_planning", "judge"])
async def test_live_structured_call(role):
    gateway = LLMGateway(configured_providers(settings), ROLES)
    try:
        session = gateway.session("live-check")
        answer = await session.structured(
            "Answer with the requested JSON only.",
            "What is the capital of France?",
            Capital,
            role=role,
        )
    finally:
        await gateway.close()

    assert answer.capital.lower() == "paris"
    usage = session.usage[0]
    assert usage.prompt_tokens > 0 and usage.completion_tokens > 0
    print(
        f"\n{role}: provider={usage.provider} model={usage.model} "
        f"in={usage.prompt_tokens} cached={usage.cached_tokens} "
        f"out={usage.completion_tokens} {usage.latency_s:.2f}s"
    )
