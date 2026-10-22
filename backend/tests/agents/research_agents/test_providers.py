import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import BaseModel, Field

from app.agents.research_agents import providers as providers_module
from app.agents.research_agents.config import CONFIG
from app.agents.research_agents.models import (
    CandidatePage,
    FreshnessMode,
    PlannedQuery,
    ResearchBrief,
)
from app.agents.research_agents.providers import (
    DownloadError,
    ExtractionError,
    MalformedContentLengthError,
    PageExtractor,
    ResponseTooLargeError,
    TavilySearch,
    UnsafeRedirectError,
)


class StructuredAnswer(BaseModel):
    answer: str = Field(min_length=3)


class RecursiveSchemaAnswer(BaseModel):
    answer: str = Field(min_length=3)

    @classmethod
    def model_json_schema(cls, *args, **kwargs) -> dict:
        return {
            "type": "object",
            "properties": {
                "answer": {"type": "string", "minLength": 3},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "rank": {"type": "integer", "minimum": 1},
                        },
                        "required": ["label"],
                    },
                },
                "optional_object": {
                    "anyOf": [
                        {
                            "type": "object",
                            "properties": {"note": {"type": "string"}},
                        },
                        {"type": "null"},
                    ],
                    "default": None,
                },
                "choice": {
                    "oneOf": [
                        {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string", "pattern": "^[A-Z]+$"}
                            },
                        },
                        {"type": "string", "enum": ["none"]},
                    ]
                },
            },
            "required": ["answer"],
        }


def run(coroutine):
    return asyncio.run(coroutine)


def make_brief(
    *,
    locale: str | None = "India",
    freshness_mode: FreshnessMode = FreshnessMode.RECENT,
    freshness_window_days: int | None = 30,
) -> ResearchBrief:
    return ResearchBrief(
        topic="AI agents",
        user_goal="Find current changes",
        required_angles=("recent changes",),
        locale=locale,
        language="en",
        freshness_mode=freshness_mode,
        freshness_window_days=freshness_window_days,
    )


def make_query(*, intent: str = "news", window: int | None = 30) -> PlannedQuery:
    return PlannedQuery(
        id="q-current",
        query="AI agent changes September 2026",
        purpose="recent changes",
        intent=intent,
        freshness_window_days=window,
    )


def make_candidate(url: str = "https://news.example.com/story") -> CandidatePage:
    return CandidatePage(
        id="candidate-1",
        url=url,
        canonical_url=url,
        publisher_domain="example.com",
        search_provider="tavily",
        title="Current story",
        snippet="Search result snippet",
        search_rank=1,
    )


async def public_resolver(host: str, port: int) -> tuple[str, ...]:
    return ("93.184.216.34",)


def test_tavily_maps_month_news_locale_and_preserves_search_metadata() -> None:
    # Break caught: sending the wrong search filters or conflating Tavily with the publisher.
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://news.example.com/story?utm_source=tavily",
                        "title": "Current story",
                        "content": "Useful search snippet, not the complete article.",
                        "published_date": "2026-09-02T10:00:00Z",
                        "score": 0.91,
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    search = TavilySearch(CONFIG, api_key="tavily-secret", http_client=client)
    pages = run(search.search(make_query(), make_brief(), 5))

    payload = json.loads(requests[0].content)
    assert payload["time_range"] == "month"
    assert payload["topic"] == "news"
    assert payload["language"] == "en"
    assert "country" not in payload
    assert payload["exclude_domains"] == sorted(CONFIG.blocked_domains)
    assert "api_key" not in payload  # the key goes only in the header
    assert requests[0].headers["authorization"] == "Bearer tavily-secret"
    assert requests[0].headers["content-type"] == "application/json"
    assert "start_date" not in payload
    assert pages[0].url == "https://news.example.com/story?utm_source=tavily"
    assert pages[0].canonical_url == "https://news.example.com/story"
    assert pages[0].search_provider == "tavily"
    assert pages[0].publisher_domain == "example.com"
    assert pages[0].snippet == "Useful search snippet, not the complete article."
    assert pages[0].published_at == datetime(2026, 9, 2, 10, tzinfo=UTC)
    assert pages[0].discovered_by == ("q-current",)
    assert pages[0].search_rank == 1
    assert pages[0].id == "q-current-9161bd5996b000d4"
    run(search.close())


@pytest.mark.parametrize("locale", ("India", "en-IN"))
def test_tavily_uses_explicit_dates_and_normalized_general_locale(locale: str) -> None:
    # Break caught: rounding a hard ten-day constraint up to a month or treating all searches as news.
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"results": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    search = TavilySearch(
        CONFIG,
        api_key="test-key",
        http_client=client,
        now=lambda: datetime(2026, 9, 4, 12, tzinfo=UTC),
    )
    run(
        search.search(
            make_query(intent="fact", window=10), make_brief(locale=locale), 3
        )
    )

    payload = json.loads(requests[0].content)
    assert payload["topic"] == "general"
    assert payload["country"] == "india"
    assert payload["start_date"] == "2026-08-25"
    assert payload["end_date"] == "2026-09-04"
    assert "time_range" not in payload
    run(search.close())


def test_tavily_never_date_filters_evergreen_and_defaults_to_the_staleness_window() -> (
    None
):
    # Break caught: an evergreen request searched within 90 days (recent news instead of guides),
    # and a search window that disagrees with the window later used to judge staleness.
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"results": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    search = TavilySearch(
        CONFIG,
        api_key="test-key",
        http_client=client,
        now=lambda: datetime(2026, 9, 4, 12, tzinfo=UTC),
    )
    evergreen_brief = make_brief(
        freshness_mode=FreshnessMode.EVERGREEN, freshness_window_days=90
    )
    run(search.search(make_query(intent="how_to", window=90), evergreen_brief, 3))
    run(
        search.search(
            make_query(intent="news", window=None),
            make_brief(freshness_window_days=None),
            3,
        )
    )

    evergreen, recent = (json.loads(request.content) for request in requests)
    assert not {"time_range", "start_date", "end_date"} & evergreen.keys()
    assert recent["start_date"] == "2026-06-06"
    run(search.close())


def test_jina_headers_are_parsed_and_markdown_body_is_preserved() -> None:
    # Break caught: leaking Jina headers into content or flattening the Markdown body.
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://r.jina.ai/https://news.example.com/story"
        return httpx.Response(
            200,
            text=(
                "Title: Parsed title\n"
                "URL Source: https://news.example.com/story\n"
                "Published Time: 2026-09-03T08:15:00Z\n"
                "Markdown Content:\n\n"
                "# Parsed title\n\n- First point\n- Second point\n"
            ),
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = PageExtractor(CONFIG, jina_client=client, resolver=public_resolver)
    document = run(extractor.extract(make_candidate()))

    assert document.candidate_id == "candidate-1"
    assert document.title == "Parsed title"
    assert document.published_at == datetime(2026, 9, 3, 8, 15, tzinfo=UTC)
    assert document.content == "# Parsed title\n\n- First point\n- Second point"
    assert document.extraction_provider == "jina"
    assert document.metadata["source_url"] == "https://news.example.com/story"
    run(extractor.close())


def test_unusable_jina_content_falls_back_to_threaded_trafilatura(monkeypatch) -> None:
    # Break caught: treating an empty Jina body as success or blocking the event loop locally.
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.host == "r.jina.ai":
            return httpx.Response(200, text="Title: Empty\nMarkdown Content:\n")
        return httpx.Response(200, text="<html><article>Source HTML</article></html>")

    class Metadata:
        title = "Fallback title"
        date = "2026-09-01"
        author = "Reporter"

    monkeypatch.setattr(
        providers_module.trafilatura,
        "extract",
        lambda html, **kwargs: "# Fallback\n\nFull article",
    )
    monkeypatch.setattr(
        providers_module,
        "extract_metadata",
        lambda html, **kwargs: Metadata(),
    )
    real_to_thread = asyncio.to_thread
    threaded_calls: list[str] = []

    async def tracking_to_thread(function, /, *args, **kwargs):
        threaded_calls.append(function.__name__)
        return await real_to_thread(function, *args, **kwargs)

    monkeypatch.setattr(providers_module.asyncio, "to_thread", tracking_to_thread)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = PageExtractor(
        CONFIG,
        jina_client=client,
        local_client=client,
        resolver=public_resolver,
    )
    document = run(extractor.extract(make_candidate()))

    assert requests == [
        "https://r.jina.ai/https://news.example.com/story",
        "https://93.184.216.34/story",
    ]
    assert threaded_calls == ["<lambda>", "<lambda>"]
    assert document.content == "# Fallback\n\nFull article"
    assert document.title == "Fallback title"
    assert document.published_at == datetime(2026, 9, 1, tzinfo=UTC)
    assert document.extraction_provider == "trafilatura"
    assert document.metadata["author"] == "Reporter"
    run(extractor.close())


def test_local_fallback_validates_every_redirect_before_following() -> None:
    # Break caught: following a public URL's redirect into a private-network target.
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host)
        if request.url.host == "r.jina.ai":
            return httpx.Response(503)
        if request.url.host == "93.184.216.34":
            return httpx.Response(
                302, headers={"location": "http://127.0.0.1/internal"}
            )
        raise AssertionError("private redirect target was requested")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = PageExtractor(
        CONFIG,
        jina_client=client,
        local_client=client,
        resolver=public_resolver,
    )
    with pytest.raises(UnsafeRedirectError):
        run(extractor.extract(make_candidate()))
    assert requested_hosts == ["r.jina.ai", "93.184.216.34"]
    run(extractor.close())


def test_local_fallback_enforces_maximum_streamed_response_size() -> None:
    # Break caught: buffering an oversized page and bypassing the configured download cap.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "r.jina.ai":
            return httpx.Response(503)
        return httpx.Response(200, content=b"01234567890")

    config = replace(CONFIG, max_download_bytes=10)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = PageExtractor(
        config,
        jina_client=client,
        local_client=client,
        resolver=public_resolver,
    )
    with pytest.raises(ResponseTooLargeError):
        run(extractor.extract(make_candidate()))
    run(extractor.close())


def test_oversized_jina_stream_stops_at_the_cap_then_local_failure_is_typed() -> None:
    # Break caught: eagerly buffering Jina content past the cap, or leaking its error when a safe fallback fails.
    class TrackingStream(httpx.AsyncByteStream):
        def __init__(self, chunks: tuple[bytes, ...]) -> None:
            self.chunks = chunks
            self.yielded: list[bytes] = []
            self.closed = False

        async def __aiter__(self):
            for chunk in self.chunks:
                self.yielded.append(chunk)
                yield chunk

        async def aclose(self) -> None:
            self.closed = True

    jina_stream = TrackingStream((b"01234", b"56789", b"X", b"unread"))
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.host == "r.jina.ai":
            return httpx.Response(200, stream=jina_stream)
        return httpx.Response(503)

    config = replace(CONFIG, max_download_bytes=10)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = PageExtractor(
        config,
        jina_client=client,
        local_client=client,
        resolver=public_resolver,
    )
    with pytest.raises(DownloadError):
        run(extractor.extract(make_candidate()))

    assert jina_stream.yielded == [b"01234", b"56789", b"X"]
    assert jina_stream.closed
    assert requested_urls == [
        "https://r.jina.ai/https://news.example.com/story",
        "https://93.184.216.34/story",
    ]
    run(extractor.close())


def test_malformed_jina_content_length_falls_back_with_a_typed_local_error() -> None:
    # Break caught: ignoring malformed Jina length metadata before reading its body.
    class TrackingStream(httpx.AsyncByteStream):
        def __init__(self) -> None:
            self.read = False

        async def __aiter__(self):
            self.read = True
            yield b"Jina body must not be read"

        async def aclose(self) -> None:
            pass

    jina_stream = TrackingStream()
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.host == "r.jina.ai":
            return httpx.Response(
                200, headers={"content-length": "many"}, stream=jina_stream
            )
        return httpx.Response(503)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = PageExtractor(
        CONFIG,
        jina_client=client,
        local_client=client,
        resolver=public_resolver,
    )
    with pytest.raises(DownloadError):
        run(extractor.extract(make_candidate()))

    assert not jina_stream.read
    assert requested_urls == [
        "https://r.jina.ai/https://news.example.com/story",
        "https://93.184.216.34/story",
    ]
    run(extractor.close())


def test_both_extractors_failing_raises_typed_error() -> None:
    # Break caught: returning an empty successful document when extraction is unusable.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "r.jina.ai":
            return httpx.Response(503)
        return httpx.Response(200, text="<html></html>")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = PageExtractor(
        CONFIG,
        jina_client=client,
        local_client=client,
        resolver=public_resolver,
    )
    with pytest.raises(ExtractionError):
        run(extractor.extract(make_candidate()))
    run(extractor.close())


def test_providers_leave_clients_they_were_given_open() -> None:
    # Break caught: closing an HTTP client that its creator still uses
    # (whoever creates a thing closes it).
    def ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    search_http = httpx.AsyncClient(transport=httpx.MockTransport(ok))
    jina_http = httpx.AsyncClient(transport=httpx.MockTransport(ok))
    local_http = httpx.AsyncClient(transport=httpx.MockTransport(ok))
    search = TavilySearch(CONFIG, api_key="test-key", http_client=search_http)
    extractor = PageExtractor(CONFIG, jina_client=jina_http, local_client=local_http)

    run(search.close())
    run(extractor.close())

    assert not (search_http.is_closed or jina_http.is_closed or local_http.is_closed)
    for client in (search_http, jina_http, local_http):
        run(client.aclose())  # the test created them, so the test closes them


def test_providers_close_the_clients_they_created() -> None:
    # Break caught: leaking connection pools a provider opened itself.
    search = TavilySearch(CONFIG, api_key="test-key")
    extractor = PageExtractor(CONFIG)

    run(search.close())
    run(extractor.close())

    assert search._client.is_closed
    assert extractor._jina_client.is_closed
    assert extractor._local_client.is_closed


@pytest.mark.parametrize(
    "address",
    (
        "127.0.0.1",
        "2002:7f00:1::1",  # 6to4 wrapping loopback
        "2002:a9fe:a9fe::1",  # 6to4 wrapping the cloud metadata IP
        "64:ff9b::a9fe:a9fe",  # NAT64 wrapping the metadata IP
    ),
)
def test_jina_prevalidation_rejects_private_dns_without_any_remote_io(
    address: str,
) -> None:
    # Break caught: proxying a public-looking hostname to Jina before rejecting a
    # non-public DNS answer, including IPv4 hidden inside IPv6.
    requested_hosts: list[str] = []

    async def private_resolver(host: str, port: int) -> tuple[str, ...]:
        assert host == "news.example.com"
        return (address,)

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.url.host)
        return httpx.Response(200, text="Markdown Content:\n\nJina must not be called")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = PageExtractor(
        CONFIG,
        jina_client=client,
        local_client=client,
        resolver=private_resolver,
    )
    with pytest.raises(UnsafeRedirectError):
        run(extractor.extract(make_candidate()))
    assert requested_hosts == []
    run(extractor.close())


@pytest.mark.parametrize("resolver_failure", ("raises", "empty"))
def test_jina_prevalidation_returns_typed_dns_error_without_any_remote_io(
    resolver_failure: str,
) -> None:
    # Break caught: failing or empty DNS resolution is bypassed by the Jina proxy request.
    requested_urls: list[str] = []

    async def unavailable_resolver(host: str, port: int) -> tuple[str, ...]:
        assert (host, port) == ("news.example.com", 443)
        if resolver_failure == "raises":
            raise OSError("resolver unavailable")
        return ()

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, text="Markdown Content:\n\nJina must not be called")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = PageExtractor(
        CONFIG,
        jina_client=client,
        local_client=client,
        resolver=unavailable_resolver,
    )
    with pytest.raises(DownloadError) as error:
        run(extractor.extract(make_candidate()))

    assert error.value.code == "dns_resolution_failed"
    assert requested_urls == []
    run(extractor.close())


def test_local_fallback_connects_to_pinned_ip_with_original_host_and_sni(
    monkeypatch,
) -> None:
    # Break caught: DNS rebinding between validation and connection, or broken HTTPS identity.
    local_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "r.jina.ai":
            return httpx.Response(503)
        local_requests.append(request)
        return httpx.Response(200, text="<html><article>Safe HTML</article></html>")

    monkeypatch.setattr(
        providers_module.trafilatura,
        "extract",
        lambda html, **kwargs: "Safe article",
    )
    monkeypatch.setattr(
        providers_module,
        "extract_metadata",
        lambda html, **kwargs: None,
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = PageExtractor(
        CONFIG,
        jina_client=client,
        local_client=client,
        resolver=public_resolver,
    )
    document = run(extractor.extract(make_candidate()))

    assert document.content == "Safe article"
    assert len(local_requests) == 1
    assert str(local_requests[0].url) == "https://93.184.216.34/story"
    assert local_requests[0].headers["host"] == "news.example.com"
    assert local_requests[0].extensions["sni_hostname"] == "news.example.com"
    run(extractor.close())


@pytest.mark.parametrize(
    "error_type", (httpx.ConnectError, httpx.ReadTimeout, httpx.ReadError)
)
def test_local_transport_failures_raise_typed_download_error(error_type) -> None:
    # Break caught: leaking raw HTTPX connection, timeout, or read errors to orchestration.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "r.jina.ai":
            return httpx.Response(503)
        raise error_type("transport failed", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = PageExtractor(
        CONFIG,
        jina_client=client,
        local_client=client,
        resolver=public_resolver,
    )
    with pytest.raises(DownloadError):
        run(extractor.extract(make_candidate()))
    run(extractor.close())


def test_malformed_content_length_raises_typed_extraction_error() -> None:
    # Break caught: leaking ValueError when a server sends malformed length metadata.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "r.jina.ai":
            return httpx.Response(503)
        return httpx.Response(200, headers={"content-length": "many"}, content=b"small")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = PageExtractor(
        CONFIG,
        jina_client=client,
        local_client=client,
        resolver=public_resolver,
    )
    with pytest.raises(MalformedContentLengthError):
        run(extractor.extract(make_candidate()))
    run(extractor.close())


@pytest.mark.parametrize("content_length", ("", "+5", "-1", "5.0", " 5", "5 ", "five"))
def test_content_length_requires_nonempty_ascii_decimal_digits(
    content_length: str,
) -> None:
    # Break caught: accepting a signed, empty, fractional, padded, or nonnumeric length.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "r.jina.ai":
            return httpx.Response(503)
        return httpx.Response(
            200, headers={"content-length": content_length}, content=b"small"
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = PageExtractor(
        CONFIG,
        jina_client=client,
        local_client=client,
        resolver=public_resolver,
    )
    with pytest.raises(MalformedContentLengthError):
        run(extractor.extract(make_candidate()))
    run(extractor.close())


def test_unicode_hostname_uses_idna_host_and_sni_with_explicit_port(
    monkeypatch,
) -> None:
    # Break caught: leaking raw Unicode into HTTP headers or losing explicit port identity.
    local_requests: list[httpx.Request] = []

    async def resolver(host: str, port: int) -> tuple[str, ...]:
        assert host == "bücher.example"
        assert port == 8443
        return ("93.184.216.34",)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "r.jina.ai":
            return httpx.Response(503)
        local_requests.append(request)
        return httpx.Response(
            200, text="<html><article>Unicode host article</article></html>"
        )

    monkeypatch.setattr(
        providers_module.trafilatura,
        "extract",
        lambda html, **kwargs: "Unicode host article",
    )
    monkeypatch.setattr(
        providers_module,
        "extract_metadata",
        lambda html, **kwargs: None,
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = PageExtractor(
        CONFIG,
        jina_client=client,
        local_client=client,
        resolver=resolver,
    )
    document = run(
        extractor.extract(make_candidate("https://bücher.example:8443/story"))
    )

    assert document.content == "Unicode host article"
    assert str(local_requests[0].url) == "https://93.184.216.34:8443/story"
    assert local_requests[0].headers["host"] == "xn--bcher-kva.example:8443"
    assert local_requests[0].extensions["sni_hostname"] == "xn--bcher-kva.example"
    run(extractor.close())


def test_header_only_jina_response_is_unusable_and_falls_back(monkeypatch) -> None:
    # Break caught: returning a Jina metadata header as if it were article content.
    local_requested = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal local_requested
        if request.url.host == "r.jina.ai":
            return httpx.Response(200, text="Title: Truncated response")
        local_requested = True
        return httpx.Response(200, text="<html><article>Complete HTML</article></html>")

    monkeypatch.setattr(
        providers_module.trafilatura,
        "extract",
        lambda html, **kwargs: "Complete article",
    )
    monkeypatch.setattr(
        providers_module,
        "extract_metadata",
        lambda html, **kwargs: None,
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    extractor = PageExtractor(
        CONFIG,
        jina_client=client,
        local_client=client,
        resolver=public_resolver,
    )
    document = run(extractor.extract(make_candidate()))

    assert local_requested
    assert document.content == "Complete article"
    assert document.extraction_provider == "trafilatura"
    run(extractor.close())


def test_tavily_reuses_a_successful_request_and_returns_independent_results() -> None:
    # Break caught: repeating provider I/O or returning cache-owned CandidatePage models to callers.
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://news.example.com/cache-story",
                        "title": "Cached story",
                        "content": "Original snippet",
                        "published_date": "2026-09-02T10:00:00Z",
                    }
                ]
            },
        )

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        search = TavilySearch(CONFIG, api_key="test-key", http_client=client)
        first = await search.search(make_query(), make_brief(), 5)
        first[0].title = "Caller mutation"
        second = await search.search(make_query(), make_brief(), 5)

        assert requests == 1
        assert second[0].title == "Cached story"
        assert first is not second
        assert first[0] is not second[0]
        await search.close()

    run(scenario())


def test_tavily_result_sensitive_input_change_bypasses_the_cache() -> None:
    # Break caught: serving English results for a search whose language or result limit changed.
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json={"results": []})

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        search = TavilySearch(CONFIG, api_key="test-key", http_client=client)
        await search.search(make_query(), make_brief(), 5)
        await search.search(
            make_query(), make_brief().model_copy(update={"language": "hi"}), 5
        )
        await search.search(make_query(), make_brief(), 3)

        assert requests == 3
        await search.close()

    run(scenario())


def test_tavily_cache_ttl_and_lru_eviction_use_the_injected_monotonic_clock() -> None:
    # Break caught: keeping entries after TTL expiry or allowing a full cache to grow indefinitely.
    now = [0.0]
    requested_queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requested_queries.append(payload["query"])
        return httpx.Response(200, json={"results": []})

    async def scenario() -> None:
        config = replace(CONFIG, cache_ttl_seconds=10, cache_maxsize=1)
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        search = TavilySearch(
            config,
            api_key="test-key",
            http_client=client,
            monotonic_clock=lambda: now[0],
        )
        first_query = make_query()
        second_query = first_query.model_copy(
            update={"query": "AI agent funding September 2026"}
        )

        await search.search(first_query, make_brief(), 5)
        await search.search(first_query, make_brief(), 5)
        await search.search(second_query, make_brief(), 5)
        await search.search(first_query, make_brief(), 5)
        now[0] = 10.0
        await search.search(first_query, make_brief(), 5)

        assert requested_queries == [
            "AI agent changes September 2026",
            "AI agent funding September 2026",
            "AI agent changes September 2026",
            "AI agent changes September 2026",
        ]
        await search.close()

    run(scenario())


def test_tavily_same_key_concurrent_searches_share_one_producer() -> None:
    # Break caught: issuing duplicate Tavily requests while an identical request is already running.
    requests = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        started.set()
        await release.wait()
        return httpx.Response(200, json={"results": []})

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        search = TavilySearch(CONFIG, api_key="test-key", http_client=client)
        first = asyncio.create_task(search.search(make_query(), make_brief(), 5))
        await started.wait()
        second = asyncio.create_task(search.search(make_query(), make_brief(), 5))
        await asyncio.sleep(0)

        assert requests == 1
        release.set()
        assert await first == []
        assert await second == []
        await search.close()

    run(scenario())


def test_tavily_cancelled_waiter_leaves_the_shared_producer_for_other_waiters() -> None:
    # Break caught: propagating one caller's cancellation into a producer another caller still needs.
    requests = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        started.set()
        await release.wait()
        return httpx.Response(200, json={"results": []})

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        search = TavilySearch(CONFIG, api_key="test-key", http_client=client)
        cancelled_waiter = asyncio.create_task(
            search.search(make_query(), make_brief(), 5)
        )
        await started.wait()
        surviving_waiter = asyncio.create_task(
            search.search(make_query(), make_brief(), 5)
        )
        await asyncio.sleep(0)
        cancelled_waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled_waiter

        assert requests == 1
        release.set()
        assert await surviving_waiter == []
        await search.close()

    run(scenario())


def test_tavily_failure_is_not_cached_and_close_cancels_pending_producers_idempotently() -> (
    None
):
    # Break caught: caching failed HTTP responses or leaving provider-owned producer tasks running on close.
    attempts = 0
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"error": "busy"})
        if attempts == 2:
            return httpx.Response(200, json={"results": []})
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.set()
            raise
        raise AssertionError("unreachable: the request hangs until it is cancelled")

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        search = TavilySearch(CONFIG, api_key="test-key", http_client=client)
        with pytest.raises(httpx.HTTPStatusError):
            await search.search(make_query(), make_brief(), 5)
        assert await search.search(make_query(), make_brief(), 5) == []

        pending = asyncio.create_task(
            search.search(
                make_query().model_copy(update={"query": "different query"}),
                make_brief(),
                5,
            )
        )
        await started.wait()
        await search.close()
        await search.close()

        with pytest.raises(asyncio.CancelledError):
            await pending
        assert attempts == 3
        assert cancelled.is_set()
        assert not client.is_closed  # given to the search, so ours to close
        await client.aclose()

    run(scenario())


def test_extractor_reuses_canonical_url_and_returns_independent_document_copies() -> (
    None
):
    # Break caught: refetching a canonical page or exposing cache-owned document metadata to callers.
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            200,
            text=(
                "Title: Cached article\n"
                "URL Source: https://news.example.com/story\n"
                "Markdown Content:\n\n"
                "Cached body"
            ),
        )

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        extractor = PageExtractor(
            CONFIG, jina_client=client, local_client=client, resolver=public_resolver
        )
        first = await extractor.extract(make_candidate())
        first.metadata["source_url"] = "caller mutation"
        second = await extractor.extract(make_candidate())

        assert requests == 1
        assert second.metadata["source_url"] == "https://news.example.com/story"
        assert first is not second
        assert first.metadata is not second.metadata
        await extractor.close()

    run(scenario())


def test_extractor_same_canonical_url_concurrent_calls_share_one_producer() -> None:
    # Break caught: duplicating full-page extraction while a matching canonical URL is in flight.
    requests = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        started.set()
        await release.wait()
        return httpx.Response(200, text="Markdown Content:\n\nConcurrent body")

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        extractor = PageExtractor(
            CONFIG, jina_client=client, local_client=client, resolver=public_resolver
        )
        first = asyncio.create_task(extractor.extract(make_candidate()))
        await started.wait()
        second = asyncio.create_task(extractor.extract(make_candidate()))
        await asyncio.sleep(0)

        assert requests == 1
        release.set()
        assert (await first).content == "Concurrent body"
        assert (await second).content == "Concurrent body"
        await extractor.close()

    run(scenario())


def test_extractor_canonical_cache_keeps_the_first_candidate_original_fetch_url() -> (
    None
):
    # Break caught: replacing a producer's meaningful source URL with its canonical identity before I/O.
    requested_urls: list[str] = []
    started = asyncio.Event()
    release = asyncio.Event()
    first_candidate = make_candidate(
        "https://news.example.com/story?edition=india"
    ).model_copy(update={"canonical_url": "https://news.example.com/story"})
    second_candidate = make_candidate(
        "https://news.example.com/story?edition=global"
    ).model_copy(
        update={"id": "candidate-2", "canonical_url": "https://news.example.com/story"}
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        started.set()
        await release.wait()
        return httpx.Response(200, text="Markdown Content:\n\nCanonical cache body")

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        extractor = PageExtractor(
            CONFIG, jina_client=client, local_client=client, resolver=public_resolver
        )
        first = asyncio.create_task(extractor.extract(first_candidate))
        await started.wait()
        second = asyncio.create_task(extractor.extract(second_candidate))
        await asyncio.sleep(0)

        assert requested_urls == [
            "https://r.jina.ai/https://news.example.com/story?edition=india"
        ]
        release.set()
        assert (await first).candidate_id == "candidate-1"
        assert (await second).candidate_id == "candidate-2"
        await extractor.close()

    run(scenario())


def test_tavily_close_rejects_different_key_arriving_after_shutdown_begins() -> None:
    # Break caught: admitting a new producer after close has started and using a closing HTTP client.
    requested_queries: list[str] = []
    first_started = asyncio.Event()
    first_cancelled = asyncio.Event()
    let_first_exit = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        query = json.loads(request.content)["query"]
        requested_queries.append(query)
        if query != "close first":
            raise AssertionError("a provider request was admitted after closing began")
        first_started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            first_cancelled.set()
            await let_first_exit.wait()
            raise
        raise AssertionError("unreachable: the request hangs until it is cancelled")

    async def scenario() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        search = TavilySearch(CONFIG, api_key="test-key", http_client=client)
        first_query = make_query().model_copy(update={"query": "close first"})
        second_query = make_query().model_copy(update={"query": "close second"})
        pending = asyncio.create_task(search.search(first_query, make_brief(), 5))
        await first_started.wait()
        closing = asyncio.create_task(search.close())
        await first_cancelled.wait()

        with pytest.raises(RuntimeError, match="closed"):
            await search.search(second_query, make_brief(), 5)
        assert requested_queries == ["close first"]

        let_first_exit.set()
        await closing
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert not client.is_closed  # given to the search, so ours to close
        await client.aclose()

    run(scenario())


def test_tavily_close_leaves_no_cache_cleanup_task_for_completed_or_cancelled_producers() -> (
    None
):
    # Break caught: fire-and-forget cache cleanup surviving close or leaving task exceptions unobserved.
    cancellation_started = asyncio.Event()
    unhandled_contexts: list[dict] = []

    class CleanupGateLock:
        def __init__(self) -> None:
            self._lock = asyncio.Lock()
            self.release_cleanup = asyncio.Event()

        async def __aenter__(self) -> None:
            current = asyncio.current_task()
            coroutine = current.get_coro() if current is not None else None
            code = getattr(coroutine, "cr_code", None)
            if (
                code is not None
                and code.co_qualname == "_AsyncTTLCache._discard_inflight"
            ):
                await self.release_cleanup.wait()
            await self._lock.acquire()

        async def __aexit__(self, exc_type, exc_value, traceback) -> None:
            self._lock.release()

    async def handler(request: httpx.Request) -> httpx.Response:
        query = json.loads(request.content)["query"]
        if query == "cleanup complete":
            return httpx.Response(200, json={"results": []})
        cancellation_started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            raise
        raise AssertionError("unreachable: the request hangs until it is cancelled")

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        previous_handler = loop.get_exception_handler()
        loop.set_exception_handler(
            lambda loop, context: unhandled_contexts.append(context)
        )
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        search = TavilySearch(CONFIG, api_key="test-key", http_client=client)
        cleanup_gate = CleanupGateLock()
        # A controllable lock on purpose, to reproduce the cleanup race.
        search._cache._lock = cleanup_gate  # pyright: ignore[reportAttributeAccessIssue]
        pending: asyncio.Task[list[CandidatePage]] | None = None
        try:
            complete_query = make_query().model_copy(
                update={"query": "cleanup complete"}
            )
            cancelled_query = make_query().model_copy(
                update={"query": "cleanup cancelled"}
            )
            assert await search.search(complete_query, make_brief(), 5) == []
            pending = asyncio.create_task(
                search.search(cancelled_query, make_brief(), 5)
            )
            await cancellation_started.wait()

            await search.close()
            with pytest.raises(asyncio.CancelledError):
                await pending
            await asyncio.sleep(0)

            owned_cleanup_tasks = [
                task
                for task in asyncio.all_tasks()
                if getattr(getattr(task.get_coro(), "cr_code", None), "co_qualname", "")
                == "_AsyncTTLCache._discard_inflight"
            ]
            assert owned_cleanup_tasks == []
            assert unhandled_contexts == []
        finally:
            cleanup_gate.release_cleanup.set()
            await asyncio.sleep(0)
            loop.set_exception_handler(previous_handler)

    run(scenario())
