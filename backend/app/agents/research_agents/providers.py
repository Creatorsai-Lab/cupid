"""Network provider adapters for the bounded research pipeline.

The adapters own long-lived ``httpx.AsyncClient`` instances, but all clients
can be injected so their complete HTTP boundary is testable without network
access.  Webpage content is returned as data only; this module never interprets
page text as instructions.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import ipaddress
import json
import logging
import re
import socket
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
import trafilatura
from pydantic import BaseModel, ValidationError
from trafilatura.metadata import extract_metadata

from app.agents.research_agents.config import CONFIG, Config
from app.agents.research_agents.filters import (
    _as_utc,
    canonicalize_url,
    early_rejection_reason,
    publisher_domain,
)
from app.agents.research_agents.models import (
    CandidatePage,
    ExtractedDocument,
    PlannedQuery,
    ResearchBrief,
)
from app.agents.research_agents.planning import _required_freshness_window

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
V = TypeVar("V")


class ProviderError(RuntimeError):
    """Base class for errors returned by an external provider."""


class RetryableProviderError(ProviderError):
    """A transient provider error which may be retried or failed over."""


class PermanentProviderError(ProviderError):
    """A provider error for which retrying the same request cannot help."""


class RateLimitedProviderError(RetryableProviderError):
    """HTTP 429: the per-minute token quota for this model is spent.

    Retrying the same model within the pipeline budget is pointless (Groq asks for ~30s),
    so the stage moves on to the next configured provider or its deterministic fallback.
    """


class ProviderCapacityError(ProviderError):
    """A request exceeds one provider's capacity and should use the next provider."""


class StructuredOutputError(ProviderError):
    """The provider response was not valid for the requested Pydantic model."""


class CircuitOpenError(ProviderError):
    """A call was rejected because its provider circuit is open."""


class ExtractionError(ProviderError):
    """Full-page extraction failed without yielding a usable document."""

    def __init__(self, candidate_id: str, code: str, message: str) -> None:
        super().__init__(message)
        self.candidate_id = candidate_id
        self.code = code


class UnsafeRedirectError(ExtractionError):
    """A local fetch redirect points to a target rejected by URL safety rules."""


class ResponseTooLargeError(ExtractionError):
    """A local fetch exceeded the configured response-size limit."""


class DownloadError(ExtractionError):
    """A local HTTP fetch failed at the connection, timeout, status, or read layer."""


class MalformedContentLengthError(ExtractionError):
    """A server supplied an invalid Content-Length header."""


class _AsyncTTLCache:
    """A small in-process TTL cache that prevents same-key request stampedes."""

    def __init__(
        self, ttl_seconds: float, maxsize: int, clock: Callable[[], float]
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._maxsize = maxsize
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._inflight: dict[str, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()
        self._closed = False
        self._close_complete = asyncio.Event()

    async def get_or_create(
        self,
        key: str,
        producer: Callable[[], Awaitable[V]],
        *,
        cacheable: Callable[[V], bool] | None = None,
    ) -> V:
        async with self._lock:
            if self._closed:
                raise RuntimeError("provider cache is closed")
            now = self._clock()
            self._discard_expired(now)
            entry = self._entries.get(key)
            if entry is not None:
                self._entries.move_to_end(key)
                return entry[1]

            task = self._inflight.get(key)
            if task is None:
                task = asyncio.create_task(self._produce(key, producer, cacheable))
                self._inflight[key] = task
                task.add_done_callback(
                    lambda completed: self._discard_inflight(key, completed)
                )
        return await asyncio.shield(task)

    async def _produce(
        self,
        key: str,
        producer: Callable[[], Awaitable[V]],
        cacheable: Callable[[V], bool] | None,
    ) -> V:
        value = await producer()
        if cacheable is None or cacheable(value):
            async with self._lock:
                if not self._closed:
                    self._store(key, value)
        return value

    def _store(self, key: str, value: Any) -> None:
        if self._ttl_seconds <= 0.0 or self._maxsize <= 0:
            return
        now = self._clock()
        self._discard_expired(now)
        while len(self._entries) >= self._maxsize:
            self._entries.popitem(last=False)
        self._entries[key] = (now + self._ttl_seconds, value)

    def _discard_expired(self, now: float) -> None:
        for key, (expires_at, _) in tuple(self._entries.items()):
            if expires_at <= now:
                del self._entries[key]

    def _discard_inflight(self, key: str, task: asyncio.Task[Any]) -> None:
        # Task callbacks run synchronously on their owning event loop. Because this
        # callback never awaits, it cannot interleave with the lock-protected
        # admission or close snapshots below.
        if self._inflight.get(key) is task:
            del self._inflight[key]
        try:
            task.exception()
        except asyncio.CancelledError:
            pass

    async def close(self) -> None:
        async with self._lock:
            if self._closed:
                already_closing = True
                tasks: tuple[asyncio.Task[Any], ...] = ()
            else:
                already_closing = False
                self._closed = True
                tasks = tuple(dict.fromkeys(self._inflight.values()))
                self._inflight.clear()
                self._entries.clear()
        if already_closing:
            await self._close_complete.wait()
            return

        for task in tasks:
            task.cancel()
        try:
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            self._close_complete.set()


@dataclass(frozen=True)
class _TavilyResult:
    url: str
    canonical_url: str
    publisher_domain: str
    title: str
    snippet: str
    published_at: datetime | None


@dataclass(frozen=True)
class _TavilyResponse:
    results: tuple[_TavilyResult, ...]
    cacheable: bool


@dataclass(frozen=True)
class _ExtractionResult:
    content: str
    title: str | None
    published_at: datetime | None
    extraction_provider: str
    metadata: dict[str, Any]


class CircuitBreaker:
    """Small asynchronous circuit breaker whose input is a lazy operation."""

    def __init__(
        self, failure_threshold: int = 3, recovery_seconds: float = 30.0
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._failures = 0
        self._opened_at: float | None = None

    async def call(self, operation: Callable[[], Awaitable[T]]) -> T:
        if self._opened_at is not None:
            if time.monotonic() - self._opened_at < self.recovery_seconds:
                raise CircuitOpenError("provider circuit is open")
            self._opened_at = None
            self._failures = 0
        try:
            result = await operation()
        except Exception:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.monotonic()
            raise
        self._failures = 0
        self._opened_at = None
        return result


class LLMClient:
    """Validated structured generation through Groq with optional NVIDIA fallback."""

    def __init__(
        self,
        config: Config = CONFIG,
        *,
        http_client: httpx.AsyncClient | None = None,
        groq_breaker: Any | None = None,
        nvidia_breaker: Any | None = None,
        retry_delays: Sequence[float] = (0.25, 0.75),
    ) -> None:
        self.config = config
        self._client = http_client or httpx.AsyncClient(timeout=httpx.Timeout(15.0))
        self._groq_breaker = groq_breaker or CircuitBreaker()
        self._groq_fast_breaker = CircuitBreaker()
        self._nvidia_breaker = nvidia_breaker or CircuitBreaker()
        self._retry_delays = tuple(retry_delays)
        self.last_provider: str | None = None

    def _provider_chain(self, role: str | None) -> list[tuple[str, str, str, str, Any]]:
        """Resolve the configured chain for a pipeline stage to concrete, credentialed providers."""
        config = self.config
        registry: dict[str, tuple[str, str, str, str, Any]] = {}
        if config.groq_api_key:
            registry["groq"] = (
                "groq",
                config.groq_base_url,
                config.groq_model,
                config.groq_api_key,
                self._groq_breaker,
            )
            if config.groq_fast_model and config.groq_fast_model != config.groq_model:
                registry["groq_fast"] = (
                    "groq_fast",
                    config.groq_base_url,
                    config.groq_fast_model,
                    config.groq_api_key,
                    self._groq_fast_breaker,
                )
        if config.nvidia_api_key:
            registry["nvidia"] = (
                "nvidia",
                config.nvidia_base_url,
                config.nvidia_model,
                config.nvidia_api_key,
                self._nvidia_breaker,
            )
        chain = {
            "planning": config.planning_provider_chain,
            "evaluation": config.evaluation_provider_chain,
        }.get(role or "", config.default_provider_chain)
        return [registry[name] for name in chain if name in registry]

    async def structured(
        self,
        system: str,
        user: str,
        response_model: type[T],
        temperature: float = 0.2,
        role: str | None = None,
    ) -> T:
        """Generate one schema-validated object, walking the stage's provider chain on failure.

        ``role`` names the pipeline stage ("planning", "evaluation") and selects its configured
        chain. Each provider generates once: an invalid answer is never repaired or resampled,
        because every extra generation spends the free-tier quota again; the caller's
        deterministic fallback takes over instead.
        """
        self.last_provider = None
        providers = self._provider_chain(role)
        if not providers:
            raise PermanentProviderError(
                "no LLM provider API key is configured for this stage"
            )

        last_error: Exception | None = None
        for provider, base_url, model, api_key, breaker in providers:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
            try:
                content = await self._complete(
                    provider,
                    base_url,
                    model,
                    api_key,
                    messages,
                    response_model,
                    temperature,
                    breaker,
                    role=role,
                )
                try:
                    result = _validate_structured(content, response_model)
                except (
                    json.JSONDecodeError,
                    ValidationError,
                    TypeError,
                    ValueError,
                ) as error:
                    raise StructuredOutputError(str(error)) from error
                self.last_provider = provider
                return result
            except (
                PermanentProviderError,
                RetryableProviderError,
                ProviderCapacityError,
                CircuitOpenError,
                StructuredOutputError,
            ) as error:
                # Every provider's failure is logged; only the last one is raised, so without
                # this line a Groq rate limit hides behind a fallback provider's error.
                _LOGGER.warning(
                    "%s structured generation failed for %s: %s",
                    provider,
                    response_model.__name__,
                    error,
                )
                last_error = error
                continue
        if last_error is not None:
            raise last_error
        raise ProviderError("structured generation failed")

    async def _complete(
        self,
        provider: str,
        base_url: str,
        model: str,
        api_key: str,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
        temperature: float,
        breaker: Any,
        *,
        role: str | None = None,
    ) -> str:
        attempts = len(self._retry_delays) + 1
        for attempt in range(attempts):
            try:
                # The coroutine is deliberately created inside this callable.  An open
                # circuit therefore cannot leave an unawaited request coroutine behind.
                return await breaker.call(
                    lambda: self._send_completion(
                        provider,
                        base_url,
                        model,
                        api_key,
                        messages,
                        response_model,
                        temperature,
                        role=role,
                    )
                )
            except (
                httpx.ConnectError,
                httpx.ConnectTimeout,
                httpx.PoolTimeout,
            ) as error:
                # The request never reached the provider, so no tokens were spent: retrying is free.
                if attempt >= attempts - 1:
                    raise RetryableProviderError(
                        f"{provider} connection failed: {error}"
                    ) from error
                await asyncio.sleep(self._retry_delays[attempt])
            except httpx.TransportError as error:
                # The request may have reached the model and spent tokens, so it is never resent.
                raise RetryableProviderError(
                    f"{provider} network request failed: {error}"
                ) from error
        raise AssertionError("unreachable")

    async def _send_completion(
        self,
        provider: str,
        base_url: str,
        model: str,
        api_key: str,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
        temperature: float,
        *,
        role: str | None = None,
    ) -> str:
        if provider.startswith("groq"):
            response_format: dict[str, Any] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": _normalize_groq_strict_schema(
                        response_model.model_json_schema()
                    ),
                },
            }
        else:
            response_format = {"type": "json_object"}

        # This is a new object on every call, so provider-specific fields cannot
        # leak into a later retry or fallback payload.
        payload = {
            "model": model,
            "messages": [dict(message) for message in messages],
            "temperature": temperature,
            "response_format": response_format,
        }
        if provider.startswith("groq"):
            payload["reasoning_effort"] = {
                "planning": self.config.planning_reasoning_effort,
                "evaluation": self.config.evaluation_reasoning_effort,
            }.get(role or "", self.config.planning_reasoning_effort)
        response = await self._client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.status_code == 413:
            raise ProviderCapacityError(f"{provider} returned HTTP 413")
        if response.status_code == 429:
            raise RateLimitedProviderError(
                f"{provider} returned HTTP 429 (per-minute token quota spent)"
            )
        if 500 <= response.status_code <= 599:
            raise RetryableProviderError(
                f"{provider} returned HTTP {response.status_code}"
            )
        if 400 <= response.status_code <= 499:
            raise PermanentProviderError(
                f"{provider} returned HTTP {response.status_code}: {_error_detail(response)}"
            )
        try:
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
            raise RetryableProviderError(
                f"{provider} returned an unusable response envelope"
            ) from error
        if not isinstance(content, str):
            raise RetryableProviderError(
                f"{provider} returned non-text structured content"
            )
        return content

    async def close(self) -> None:
        await self._client.aclose()


class TavilySearch:
    """Tavily search adapter which returns snippets with explicit provenance."""

    def __init__(
        self,
        config: Config = CONFIG,
        *,
        http_client: httpx.AsyncClient | None = None,
        now: Callable[[], datetime] | None = None,
        monotonic_clock: Callable[[], float] | None = None,
    ) -> None:
        self.config = config
        self._client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(10.0), trust_env=False
        )
        self._owns_client = http_client is None
        self._now = now or (lambda: datetime.now(UTC))
        self._cache = _AsyncTTLCache(
            config.cache_ttl_seconds,
            config.cache_maxsize,
            monotonic_clock or time.monotonic,
        )

    async def search(
        self,
        query: PlannedQuery,
        brief: ResearchBrief,
        max_results: int,
    ) -> list[CandidatePage]:
        payload = self._search_payload(query, brief, max_results)
        response = await self._cache.get_or_create(
            _cache_key(payload),
            lambda: self._search_uncached(payload),
            cacheable=lambda result: result.cacheable,
        )
        pages: list[CandidatePage] = []
        for rank, item in enumerate(response.results, start=1):
            identity = hashlib.sha256(
                f"{query.id}\0{item.canonical_url}".encode()
            ).hexdigest()[:16]
            pages.append(
                CandidatePage(
                    id=f"{query.id}-{identity}",
                    url=item.url,
                    canonical_url=item.canonical_url,
                    publisher_domain=item.publisher_domain,
                    search_provider="tavily",
                    title=item.title,
                    snippet=item.snippet,
                    published_at=item.published_at,
                    discovered_by=(query.id,),
                    search_rank=rank,
                )
            )
        return pages

    def _search_payload(
        self,
        query: PlannedQuery,
        brief: ResearchBrief,
        max_results: int,
    ) -> dict[str, Any]:
        normalized_query = " ".join(query.query.split())
        payload: dict[str, Any] = {
            "query": normalized_query,
            "max_results": max_results,
            "topic": "news" if query.intent.strip().lower() == "news" else "general",
            "language": brief.language.strip().lower(),
            "exclude_domains": sorted(self.config.blocked_domains),
            "include_raw_content": False,
        }
        if payload["topic"] == "general":
            country = _tavily_country(brief.locale)
            if country:
                payload["country"] = country
        # An evergreen brief is never date-filtered, whatever window its query lane carries.
        window = _required_freshness_window(brief)
        if window is not None:
            window = query.freshness_window_days or window
        bucket = (
            {
                1: "day",
                7: "week",
                30: "month",
                31: "month",
                365: "year",
                366: "year",
            }.get(window)
            if window is not None
            else None
        )
        if bucket:
            payload["time_range"] = bucket
        elif window is not None:
            current = _as_utc(self._now())
            payload["start_date"] = (
                (current - timedelta(days=window)).date().isoformat()
            )
            payload["end_date"] = current.date().isoformat()
        return payload

    async def _search_uncached(self, payload: dict[str, Any]) -> _TavilyResponse:
        response = await self._client.post(
            "https://api.tavily.com/search",
            headers={
                "Authorization": f"Bearer {self.config.tavily_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as error:
            raise ProviderError("Tavily returned invalid JSON") from error
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise ProviderError("Tavily returned an unusable response envelope")

        cacheable = True
        results: list[_TavilyResult] = []
        for item in data["results"]:
            if not isinstance(item, dict):
                cacheable = False
                continue
            url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()
            if not url or not title:
                cacheable = False
                continue
            canonical_url = canonicalize_url(url)
            domain = publisher_domain(url)
            if not canonical_url or not domain:
                cacheable = False
                continue
            results.append(
                _TavilyResult(
                    url=url,
                    canonical_url=canonical_url,
                    publisher_domain=domain,
                    title=title,
                    snippet=str(item.get("content") or ""),
                    published_at=_parse_datetime(item.get("published_date")),
                )
            )
        return _TavilyResponse(results=tuple(results), cacheable=cacheable)

    async def close(self) -> None:
        await self._cache.close()
        if self._owns_client:  # a client we were given belongs to its creator
            await self._client.aclose()


class PageExtractor:
    """Jina Reader extraction with a bounded, redirect-safe local fallback."""

    def __init__(
        self,
        config: Config = CONFIG,
        *,
        jina_client: httpx.AsyncClient | None = None,
        local_client: httpx.AsyncClient | None = None,
        resolver: Callable[[str, int], Awaitable[Sequence[str]]] | None = None,
        max_redirects: int = 3,
        monotonic_clock: Callable[[], float] | None = None,
    ) -> None:
        self.config = config
        self._jina_client = jina_client or httpx.AsyncClient(
            timeout=httpx.Timeout(12.0),
            trust_env=False,
        )
        self._local_client = local_client or httpx.AsyncClient(
            timeout=httpx.Timeout(12.0),
            trust_env=False,
        )
        self._owned_clients = tuple(
            client
            for client, given in (
                (self._jina_client, jina_client),
                (self._local_client, local_client),
            )
            if given is None
        )
        self._resolver = resolver or _resolve_public_addresses
        self._max_redirects = max_redirects
        self._cache = _AsyncTTLCache(
            config.cache_ttl_seconds,
            config.cache_maxsize,
            monotonic_clock or time.monotonic,
        )

    async def extract(self, candidate: CandidatePage) -> ExtractedDocument:
        rejection = early_rejection_reason(candidate.url, candidate.title, self.config)
        if rejection is not None:
            raise ExtractionError(
                candidate.id, rejection, f"candidate URL was rejected: {rejection}"
            )
        result = await self._cache.get_or_create(
            self._cache_key(candidate.canonical_url),
            lambda: self._extract_uncached(candidate),
            cacheable=lambda extracted: bool(extracted.content.strip()),
        )
        return ExtractedDocument(
            candidate_id=candidate.id,
            content=result.content,
            title=result.title or candidate.title,
            published_at=result.published_at or candidate.published_at,
            extraction_provider=result.extraction_provider,
            metadata=copy.deepcopy(result.metadata),
        )

    def _cache_key(self, canonical_url: str) -> str:
        return _cache_key(
            {
                "canonical_url": canonical_url,
                "jina_reader_base_url": self.config.jina_reader_base_url,
                "max_download_bytes": self.config.max_download_bytes,
                "minimum_article_chars": self.config.minimum_article_chars,
                "max_clean_content_chars": self.config.max_clean_content_chars,
                "max_redirects": self._max_redirects,
            }
        )

    async def _extract_uncached(self, candidate: CandidatePage) -> _ExtractionResult:
        # Resolve and validate the original target before disclosing it to Jina.
        # The Jina URL intentionally remains unpinned; the local fallback pins each
        # connection (including redirects) independently below.
        await self._pin_url(candidate, candidate.url)
        try:
            jina_document = await self._extract_jina(candidate)
            if jina_document is not None:
                return jina_document
        except (httpx.HTTPError, ExtractionError):
            pass
        return await self._extract_local(candidate)

    async def _extract_jina(self, candidate: CandidatePage) -> _ExtractionResult | None:
        async with self._jina_client.stream(
            "GET", self._jina_url(candidate.url)
        ) as response:
            response.raise_for_status()
            text = await self._read_bounded_response(candidate, response)
        title, source_url, published_at, body = _parse_jina(text)
        if not body.strip():
            return None
        return _ExtractionResult(
            content=body.strip(),
            title=title,
            published_at=published_at,
            extraction_provider="jina",
            metadata={"source_url": source_url or candidate.url},
        )

    async def _read_bounded_response(
        self, candidate: CandidatePage, response: httpx.Response
    ) -> str:
        declared_size = response.headers.get("content-length")
        if declared_size is not None:
            if re.fullmatch(r"[0-9]+", declared_size, flags=re.ASCII) is None:
                raise MalformedContentLengthError(
                    candidate.id,
                    "malformed_content_length",
                    "response has malformed Content-Length",
                )
            parsed_size = int(declared_size)
            if parsed_size > self.config.max_download_bytes:
                raise ResponseTooLargeError(
                    candidate.id,
                    "response_too_large",
                    "response exceeds configured download limit",
                )
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > self.config.max_download_bytes:
                raise ResponseTooLargeError(
                    candidate.id,
                    "response_too_large",
                    "response exceeds configured download limit",
                )
            chunks.append(chunk)
        encoding = response.encoding or "utf-8"
        return b"".join(chunks).decode(encoding, errors="replace")

    def _jina_url(self, url: str) -> str:
        base = self.config.jina_reader_base_url
        # Strip legacy trailing scheme suffix (e.g. "https://r.jina.ai/http://")
        for suffix in ("http://", "https://"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        return f"{base.rstrip('/')}/{url}"

    async def _extract_local(self, candidate: CandidatePage) -> _ExtractionResult:
        final_url, html = await self._download(candidate)
        try:
            content = await asyncio.to_thread(
                trafilatura.extract,
                html,
                url=final_url,
                output_format="markdown",
                include_links=True,
                include_images=False,
            )
            page_metadata = await asyncio.to_thread(
                extract_metadata, html, default_url=final_url
            )
        except Exception as error:
            raise ExtractionError(
                candidate.id, "local_extraction_failed", str(error)
            ) from error
        if not content or not content.strip():
            raise ExtractionError(
                candidate.id, "empty_content", "Trafilatura returned no usable content"
            )

        title = getattr(page_metadata, "title", None) if page_metadata else None
        published_at = (
            _parse_datetime(getattr(page_metadata, "date", None))
            if page_metadata
            else None
        )
        metadata: dict[str, Any] = {"source_url": final_url}
        if page_metadata:
            for field in ("author", "description", "sitename", "categories", "tags"):
                value = getattr(page_metadata, field, None)
                if value:
                    metadata[field] = value
        return _ExtractionResult(
            content=content.strip(),
            title=title,
            published_at=published_at,
            extraction_provider="trafilatura",
            metadata=metadata,
        )

    async def _download(self, candidate: CandidatePage) -> tuple[str, str]:
        current_url = candidate.url
        for redirect_count in range(self._max_redirects + 1):
            if (
                early_rejection_reason(current_url, candidate.title, self.config)
                is not None
            ):
                raise UnsafeRedirectError(
                    candidate.id,
                    "unsafe_redirect",
                    f"unsafe redirect target: {current_url}",
                )
            pinned_url, host_header, sni_hostname = await self._pin_url(
                candidate, current_url
            )
            try:
                async with self._local_client.stream(
                    "GET",
                    pinned_url,
                    headers={"Host": host_header, "Connection": "close"},
                    extensions={"sni_hostname": sni_hostname},
                    follow_redirects=False,
                ) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise ExtractionError(
                                candidate.id,
                                "invalid_redirect",
                                "redirect omitted Location",
                            )
                        if redirect_count >= self._max_redirects:
                            raise ExtractionError(
                                candidate.id,
                                "too_many_redirects",
                                "redirect limit exceeded",
                            )
                        next_url = urljoin(current_url, location)
                        if (
                            early_rejection_reason(
                                next_url, candidate.title, self.config
                            )
                            is not None
                        ):
                            raise UnsafeRedirectError(
                                candidate.id,
                                "unsafe_redirect",
                                f"unsafe redirect target: {next_url}",
                            )
                        current_url = next_url
                        continue
                    response.raise_for_status()
                    return current_url, await self._read_bounded_response(
                        candidate, response
                    )
            except ExtractionError:
                raise
            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.HTTPError,
            ) as error:
                raise DownloadError(
                    candidate.id,
                    "download_failed",
                    f"local fetch failed: {error}",
                ) from error
            except (UnicodeError, httpx.InvalidURL) as error:
                raise DownloadError(
                    candidate.id,
                    "request_build_failed",
                    f"local request could not be encoded: {error}",
                ) from error
        raise ExtractionError(
            candidate.id, "too_many_redirects", "redirect limit exceeded"
        )

    async def _pin_url(
        self, candidate: CandidatePage, url: str
    ) -> tuple[str, str, str]:
        parsed = urlsplit(url)
        hostname = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        try:
            literal = ipaddress.ip_address(hostname)
            addresses = (str(literal),)
        except ValueError:
            try:
                addresses = tuple(await self._resolver(hostname, port))
            except (TimeoutError, OSError) as error:
                raise DownloadError(
                    candidate.id,
                    "dns_resolution_failed",
                    f"DNS resolution failed for {hostname}: {error}",
                ) from error
        if not addresses:
            raise DownloadError(
                candidate.id,
                "dns_resolution_failed",
                f"DNS returned no addresses for {hostname}",
            )

        normalized: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
        for address in addresses:
            try:
                parsed_address = ipaddress.ip_address(address)
            except ValueError as error:
                raise UnsafeRedirectError(
                    candidate.id,
                    "unsafe_resolved_address",
                    f"DNS returned an invalid address for {hostname}",
                ) from error
            if _unsafe_address(parsed_address):
                raise UnsafeRedirectError(
                    candidate.id,
                    "unsafe_resolved_address",
                    f"DNS returned a non-public address for {hostname}",
                )
            normalized.append(parsed_address)

        selected = normalized[0]
        pinned_host = f"[{selected}]" if selected.version == 6 else str(selected)
        default_port = 443 if parsed.scheme.lower() == "https" else 80
        pinned_netloc = pinned_host if port == default_port else f"{pinned_host}:{port}"
        try:
            ascii_hostname = hostname.encode("idna").decode("ascii")
        except UnicodeError as error:
            raise DownloadError(
                candidate.id,
                "invalid_hostname_encoding",
                f"hostname could not be IDNA encoded: {hostname!r}",
            ) from error
        original_host = (
            f"[{ascii_hostname}]" if ":" in ascii_hostname else ascii_hostname
        )
        host_header = (
            original_host if port == default_port else f"{original_host}:{port}"
        )
        pinned_url = urlunsplit(
            (parsed.scheme, pinned_netloc, parsed.path, parsed.query, "")
        )
        return pinned_url, host_header, ascii_hostname

    async def close(self) -> None:
        await self._cache.close()
        for (
            client
        ) in self._owned_clients:  # clients we were given belong to their creator
            await client.aclose()


def _error_detail(response: httpx.Response) -> str:
    """Return a bounded, single-line description of a provider error body for diagnostics."""
    try:
        body = response.json()
    except ValueError:
        body = response.text
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict):
            body = " ".join(
                str(error.get(key))
                for key in ("code", "type", "message")
                if error.get(key)
            )
    return re.sub(r"\s+", " ", str(body))[:200]


def _validate_structured[M: BaseModel](content: str, response_model: type[M]) -> M:

    text = content.strip()
    fenced = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL
    )
    if fenced:
        text = fenced.group(1).strip()
    return response_model.model_validate(json.loads(text))


def _normalize_groq_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a non-mutating Groq-strict copy of a JSON schema."""

    normalized = copy.deepcopy(schema)

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

    visit(normalized)
    return normalized


def _parse_jina(text: str) -> tuple[str | None, str | None, datetime | None, str]:
    title: str | None = None
    source_url: str | None = None
    published_at: datetime | None = None
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    body_start = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            body_start = index + 1
            continue
        if stripped.lower().startswith("title:"):
            title = stripped.split(":", 1)[1].strip() or None
            body_start = index + 1
        elif stripped.lower().startswith("url source:"):
            source_url = stripped.split(":", 1)[1].strip() or None
            body_start = index + 1
        elif stripped.lower().startswith("published time:"):
            published_at = _parse_datetime(stripped.split(":", 1)[1].strip())
            body_start = index + 1
        elif stripped.lower().startswith("markdown content:"):
            body_start = index + 1
            break
        else:
            body_start = index
            break
    return title, source_url, published_at, "\n".join(lines[body_start:]).strip()


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return _as_utc(parsed)


def _cache_key(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


async def _resolve_public_addresses(hostname: str, port: int) -> tuple[str, ...]:
    loop = asyncio.get_running_loop()
    records = await loop.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    return tuple(dict.fromkeys(str(record[4][0]) for record in records))


def _unsafe_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_reserved,
            address.is_multicast,
            address.is_unspecified,
            not address.is_global,
        )
    )


def _tavily_country(locale: str | None) -> str | None:
    if not locale:
        return None
    normalized = locale.strip().lower().replace("_", "-")
    country_aliases = {
        "au": "australia",
        "br": "brazil",
        "ca": "canada",
        "de": "germany",
        "es": "spain",
        "fr": "france",
        "gb": "united kingdom",
        "in": "india",
        "it": "italy",
        "jp": "japan",
        "mx": "mexico",
        "us": "united states",
    }
    country_names = frozenset(country_aliases.values())
    if normalized in country_names:
        return normalized
    locale_country = normalized.rsplit("-", 1)[-1]
    return country_aliases.get(locale_country)


__all__ = [
    "CircuitBreaker",
    "CircuitOpenError",
    "DownloadError",
    "ExtractionError",
    "LLMClient",
    "MalformedContentLengthError",
    "PageExtractor",
    "PermanentProviderError",
    "ProviderCapacityError",
    "ProviderError",
    "ResponseTooLargeError",
    "RetryableProviderError",
    "StructuredOutputError",
    "TavilySearch",
    "UnsafeRedirectError",
]
