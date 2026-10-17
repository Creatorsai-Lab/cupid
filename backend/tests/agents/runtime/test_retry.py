"""When a failed pipeline step is retried: only transient errors that a fresh
attempt can fix within seconds. Everything else fails the run (resumable)."""

import httpx
import pytest
from pydantic import BaseModel, ValidationError

from app.agents.llm.errors import (
    NoProviderAvailableError,
    PermanentProviderError,
    ProviderCapacityError,
    RateLimitedError,
    RetryableProviderError,
    StructuredOutputError,
)
from app.agents.runtime.retry import STEP_RETRY, resume_later, should_retry_step


def validation_error() -> ValidationError:
    class Model(BaseModel):
        n: int

    try:
        Model.model_validate({"n": "x"})
    except ValidationError as error:
        return error
    raise AssertionError("expected a validation error")


@pytest.mark.parametrize(
    "error",
    [
        RetryableProviderError("HTTP 503"),
        ConnectionError("reset"),
        ConnectionResetError("reset by peer"),
        TimeoutError("slow"),
        httpx.ReadTimeout("slow"),
        httpx.ConnectError("refused"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_transient_errors_are_retried(error):
    assert should_retry_step(error) is True


@pytest.mark.parametrize(
    "error",
    [
        RateLimitedError("HTTP 429"),  # a RetryableProviderError, but needs ~30 s
        NoProviderAvailableError("all cooling down"),
        PermissionError(
            "research may not write 'plan'"
        ),  # an OSError, like connection errors
        FileNotFoundError("missing"),
        StructuredOutputError("bad JSON from every provider"),
        PermanentProviderError("HTTP 401"),
        ProviderCapacityError("HTTP 413"),
        validation_error(),
        ValueError("bug"),
        KeyError("bug"),
        RuntimeError("unknown"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_everything_else_is_not_retried(error):
    assert should_retry_step(error) is False


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (RateLimitedError("429"), True),
        (NoProviderAvailableError("cooling"), True),
        (RetryableProviderError("503"), False),
        (PermissionError("bug"), False),
    ],
    ids=lambda v: type(v).__name__ if isinstance(v, Exception) else str(v),
)
def test_quota_errors_are_resumed_later_by_the_runtime(error, expected):
    assert resume_later(error) is expected


def test_policy_uses_our_rule_with_a_bounded_backoff():
    assert STEP_RETRY.retry_on is should_retry_step
    assert STEP_RETRY.max_attempts == 3
    assert STEP_RETRY.initial_interval == 1.0
    assert STEP_RETRY.max_interval <= 10.0
