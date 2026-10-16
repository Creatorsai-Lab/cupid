"""FakeLLM must behave like LLMSession where tests depend on it."""

import inspect

import pytest
from pydantic import BaseModel

from app.agents.llm.errors import RateLimitedError
from app.agents.llm.gateway import LLMSession
from tests.fakes import FakeLLM


class Answer(BaseModel):
    text: str


def test_fake_has_the_same_structured_signature_as_the_real_session():
    real = inspect.signature(LLMSession.structured)
    fake = inspect.signature(FakeLLM.structured)
    assert list(real.parameters) == list(fake.parameters)


async def test_fake_returns_queued_answers_and_records_calls():
    llm = FakeLLM({"text": "one"}, Answer(text="two"), RateLimitedError("busy"))

    assert await llm.structured("s", "u1", Answer, role="writer") == Answer(text="one")
    assert await llm.structured("s", "u2", Answer, role="writer") == Answer(text="two")
    with pytest.raises(RateLimitedError):
        await llm.structured("s", "u3", Answer, role="writer")
    assert [c["user"] for c in llm.calls] == ["u1", "u2", "u3"]
