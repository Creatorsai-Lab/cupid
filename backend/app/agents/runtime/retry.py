"""When a failed pipeline step is retried (plan 5.6).

A step is retried only when a fresh attempt can plausibly succeed within
seconds. LangGraph's default rule never retries RuntimeError subclasses (all
our provider errors), so we use our own, explicit allow-list.

- Retried: transient provider and network errors.
- Resumed later by the runtime (not retried here): quota errors, which need
  the provider's cooldown (~30 s+) to pass.
- Never retried: code bugs (ownership, validation), errors every provider
  already failed on, and anything unknown. Retrying those hides bugs or burns
  quota.

Only the raised error itself is classified, not its cause: steps must raise
our typed errors (app.agents.llm.errors) for failures they know are transient.
"""

import httpx
from langgraph.types import RetryPolicy

from app.agents.llm.errors import (
    NoProviderAvailableError,
    RateLimitedError,
    RetryableProviderError,
)


class StepFailedError(Exception):
    """A step's attempt failed in a way another attempt may fix (e.g. research
    found nothing). Retried like a transient error; if every attempt fails, the
    user sees `user_message` instead of the generic error."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


# Specific classes only: PermissionError is an OSError too, so OSError must not be here.
_TRANSIENT = (
    RetryableProviderError,
    ConnectionError,
    TimeoutError,
    httpx.TransportError,
)
_QUOTA = (RateLimitedError, NoProviderAvailableError)


def should_retry_step(error: Exception) -> bool:
    """True if retrying the failed step within seconds can succeed."""
    if isinstance(error, _QUOTA):  # RateLimitedError is a RetryableProviderError
        return False
    return isinstance(error, (*_TRANSIENT, StepFailedError))


def resume_later(error: BaseException) -> bool:
    """True if the run should be resumed automatically once provider quota recovers."""
    return isinstance(error, _QUOTA)


STEP_RETRY = RetryPolicy(
    max_attempts=3,
    initial_interval=1.0,
    backoff_factor=2.0,
    max_interval=10.0,
    jitter=True,
    retry_on=should_retry_step,
)
