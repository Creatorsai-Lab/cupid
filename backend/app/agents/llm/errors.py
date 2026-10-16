"""Errors raised by the LLM gateway. Retryable errors move a call to the next
provider; permanent ones mean retrying the same request cannot help."""


class ProviderError(RuntimeError):
    """Base class for errors returned by an LLM provider."""


class RetryableProviderError(ProviderError):
    """A transient failure (5xx, timeout, unusable response): try the next provider."""


class RateLimitedError(RetryableProviderError):
    """HTTP 429: the provider's quota is spent; it cools down before the next use."""


class PermanentProviderError(ProviderError):
    """A 4xx the same request can't recover from (bad key, bad request)."""


class ProviderCapacityError(ProviderError):
    """HTTP 413: the request is too large for this provider."""


class StructuredOutputError(ProviderError):
    """The answer was not valid JSON for the requested schema."""


class NoProviderAvailableError(ProviderError):
    """No configured provider can serve the role right now."""
