"""LLM gateway: provider choice per run, failover, cooldown, retries, structured
output and usage accounting. HTTP is faked with respx; nothing hits the network."""

import json

import httpx
import pytest
import respx
from fakeredis import FakeAsyncRedis
from pydantic import BaseModel

from app.agents.llm.errors import (
    NoProviderAvailableError,
    PermanentProviderError,
    StructuredOutputError,
)
from app.agents.llm.gateway import LLMGateway, RedisCooldowns
from app.agents.llm.roles import ROLES, ProviderSpec, RoleSpec, configured_providers
from app.config import Settings

PRIMARY = "https://primary.test/v1/chat/completions"
BACKUP = "https://backup.test/v1/chat/completions"


class Answer(BaseModel):
    text: str


def provider(name: str, url: str, **fields) -> ProviderSpec:
    return ProviderSpec(
        name=name,
        base_url=url.removesuffix("/chat/completions"),
        model=f"{name}-model",
        api_key=f"{name}-key",
        **fields,
    )


def completion(
    content: str, *, prompt=10, completion_tokens=5, cached: int | None = 0
) -> httpx.Response:
    usage: dict = {"prompt_tokens": prompt, "completion_tokens": completion_tokens}
    if cached is not None:  # None: the provider doesn't report caching at all
        usage["prompt_tokens_details"] = {"cached_tokens": cached}
    return httpx.Response(
        200, json={"choices": [{"message": {"content": content}}], "usage": usage}
    )


OK = completion('{"text": "hi"}')


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def no_sleep(_: float) -> None:
    return None


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def gateway(clock):
    gw = LLMGateway(
        providers={
            "primary": provider("primary", PRIMARY, strict_schema=True),
            "backup": provider(
                "backup", BACKUP, extra_body={"provider": {"data_collection": "deny"}}
            ),
        },
        roles={
            "writer": RoleSpec(providers=("primary", "backup"), timeout_s=12.0),
            "judge": RoleSpec(providers=("backup",), timeout_s=5.0),
        },
        clock=clock,
        sleep=no_sleep,
    )
    yield gw


def sent(route: respx.Route, call: int = -1) -> dict:
    return json.loads(route.calls[call].request.content)


async def ask(session, role: str = "writer") -> Answer:
    return await session.structured("system", "user", Answer, role=role)


# ── Structured output ──────────────────────────────────────────


@respx.mock
async def test_returns_validated_object_and_requests_strict_schema(gateway):
    route = respx.post(PRIMARY).mock(return_value=OK)

    answer = await ask(gateway.session("run-1"))

    assert answer == Answer(text="hi")
    body = sent(route)
    assert body["model"] == "primary-model"
    assert body["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user"},
    ]
    schema = body["response_format"]["json_schema"]
    assert schema["strict"] is True
    assert schema["schema"]["additionalProperties"] is False
    assert route.calls[0].request.headers["Authorization"] == "Bearer primary-key"


@respx.mock
async def test_accepts_json_wrapped_in_a_code_fence(gateway):
    respx.post(PRIMARY).mock(return_value=completion('```json\n{"text": "hi"}\n```'))
    assert await ask(gateway.session("run-1")) == Answer(text="hi")


@respx.mock
async def test_invalid_output_fails_over_without_resampling(gateway):
    primary = respx.post(PRIMARY).mock(return_value=completion('{"wrong": 1}'))
    backup = respx.post(BACKUP).mock(return_value=OK)

    assert await ask(gateway.session("run-1")) == Answer(text="hi")
    assert primary.call_count == 1  # never asked twice: each try spends quota
    assert sent(backup)["response_format"] == {"type": "json_object"}


@respx.mock
async def test_all_providers_failing_raises_the_last_error(gateway):
    respx.post(PRIMARY).mock(return_value=completion("not json"))
    respx.post(BACKUP).mock(return_value=completion("still not json"))
    with pytest.raises(StructuredOutputError):
        await ask(gateway.session("run-1"))


# ── Failover, stickiness, cooldown ─────────────────────────────


@respx.mock
async def test_rate_limit_fails_over_and_the_run_sticks_to_the_backup(gateway):
    primary = respx.post(PRIMARY).mock(
        return_value=httpx.Response(429, headers={"Retry-After": "20"})
    )
    backup = respx.post(BACKUP).mock(return_value=OK)
    session = gateway.session("run-1")

    await ask(session)
    await ask(session)

    assert primary.call_count == 1
    assert backup.call_count == 2


@respx.mock
async def test_rate_limited_provider_cools_down_for_every_run(gateway, clock):
    primary = respx.post(PRIMARY)
    primary.side_effect = [httpx.Response(429, headers={"Retry-After": "20"}), OK]
    backup = respx.post(BACKUP).mock(return_value=OK)

    await ask(gateway.session("run-1"))
    await ask(gateway.session("run-2"))  # still cooling: goes straight to backup
    assert (primary.call_count, backup.call_count) == (1, 2)

    clock.now += 21
    await ask(gateway.session("run-3"))  # cooled down: preferred provider again
    assert primary.call_count == 2


@respx.mock
async def test_new_run_prefers_the_first_provider_again(gateway):
    primary = respx.post(PRIMARY)
    primary.side_effect = [httpx.Response(503), OK]
    respx.post(BACKUP).mock(return_value=OK)

    await ask(gateway.session("run-1"))  # 503: fails over, no cooldown
    await ask(gateway.session("run-2"))
    assert primary.call_count == 2


@respx.mock
async def test_only_connection_failures_are_retried(gateway):
    primary = respx.post(PRIMARY)
    primary.side_effect = [httpx.ConnectError("refused"), OK]
    assert await ask(gateway.session("run-1")) == Answer(text="hi")
    assert primary.call_count == 2  # request never reached the model: free to retry


@respx.mock
async def test_failures_after_sending_are_never_resent(gateway):
    primary = respx.post(PRIMARY).mock(side_effect=httpx.ReadTimeout("slow"))
    backup = respx.post(BACKUP).mock(return_value=OK)
    assert await ask(gateway.session("run-1")) == Answer(text="hi")
    assert (primary.call_count, backup.call_count) == (1, 1)


@respx.mock
async def test_client_errors_fail_over_and_report_a_permanent_error(gateway):
    respx.post(PRIMARY).mock(
        return_value=httpx.Response(401, json={"error": "bad key"})
    )
    respx.post(BACKUP).mock(return_value=httpx.Response(400, json={"error": "bad"}))
    with pytest.raises(PermanentProviderError):
        await ask(gateway.session("run-1"))


async def test_role_without_configured_providers_is_an_error(clock):
    gw = LLMGateway(
        providers={},
        roles={"writer": RoleSpec(providers=("primary",), timeout_s=5.0)},
        clock=clock,
        sleep=no_sleep,
    )
    with pytest.raises(NoProviderAvailableError):
        await ask(gw.session("run-1"))


# ── Request options and accounting ─────────────────────────────


@respx.mock
async def test_provider_extra_fields_go_only_to_that_provider(gateway):
    primary = respx.post(PRIMARY).mock(return_value=OK)
    backup = respx.post(BACKUP).mock(return_value=OK)

    await ask(gateway.session("run-1"), role="writer")
    await ask(gateway.session("run-2"), role="judge")

    assert "provider" not in sent(primary)
    assert sent(backup)["provider"] == {"data_collection": "deny"}


@respx.mock
async def test_role_timeout_is_applied(gateway):
    route = respx.post(PRIMARY).mock(return_value=OK)
    await ask(gateway.session("run-1"))
    assert route.calls[0].request.extensions["timeout"]["read"] == 12.0


@respx.mock
async def test_usage_is_recorded_per_call_with_cached_tokens(gateway):
    respx.post(PRIMARY).mock(
        return_value=completion(
            '{"text": "hi"}', prompt=1200, completion_tokens=80, cached=1024
        )
    )
    session = gateway.session("run-1")

    await ask(session)
    await ask(session)

    first = session.usage[0]
    assert (first.run_id, first.role, first.provider, first.model) == (
        "run-1",
        "writer",
        "primary",
        "primary-model",
    )
    assert (first.prompt_tokens, first.completion_tokens, first.cached_tokens) == (
        1200,
        80,
        1024,
    )
    assert session.totals() == {
        "prompt_tokens": 2400,
        "completion_tokens": 160,
        "cached_tokens": 2048,
    }


def test_api_keys_never_appear_in_provider_repr():
    spec = provider("primary", PRIMARY)
    assert "primary-key" not in repr(spec)


@respx.mock
async def test_reasoning_effort_goes_only_to_providers_that_accept_it(clock):
    gw = LLMGateway(
        providers={
            "primary": provider("primary", PRIMARY, reasoning_effort=True),
            "backup": provider("backup", BACKUP),
        },
        roles={"writer": RoleSpec(("primary", "backup"), reasoning_effort="low")},
        clock=clock,
        sleep=no_sleep,
    )
    primary = respx.post(PRIMARY).mock(return_value=httpx.Response(503))
    backup = respx.post(BACKUP).mock(return_value=OK)

    await ask(gw.session("run-1"))

    assert sent(primary)["reasoning_effort"] == "low"
    assert "reasoning_effort" not in sent(backup)


# ── Role configuration ─────────────────────────────────────────


def settings_with(**values) -> Settings:
    """Settings from values only; never reads backend/.env."""
    return Settings.model_validate({"secret_key": "k" * 40, **values})


def test_every_role_uses_known_providers():
    providers = configured_providers(settings_with(groq_api_key="test-key"))
    for role, spec in ROLES.items():
        assert set(spec.providers) <= set(providers), role


def test_providers_without_an_api_key_are_skipped():
    assert configured_providers(settings_with(groq_api_key="")) == {}


@respx.mock
async def test_unreported_caching_is_unknown_not_zero(gateway):
    """Groq's free tier reports no cache data; that must not look like a 0% hit rate."""
    respx.post(PRIMARY).mock(return_value=completion('{"text": "hi"}', cached=None))
    session = gateway.session("run-1")

    await ask(session)

    assert session.usage[0].cached_tokens is None
    assert session.totals()["cached_tokens"] is None


# ── Cooldowns shared across worker processes ───────────────────


@respx.mock
async def test_redis_cooldown_is_shared_by_every_worker():
    redis = FakeAsyncRedis(decode_responses=True)
    roles = {"writer": RoleSpec(("primary", "backup"))}
    providers = {
        "primary": provider("primary", PRIMARY),
        "backup": provider("backup", BACKUP),
    }
    worker_a = LLMGateway(
        providers, roles, cooldowns=RedisCooldowns(redis), sleep=no_sleep
    )
    worker_b = LLMGateway(
        providers, roles, cooldowns=RedisCooldowns(redis), sleep=no_sleep
    )
    primary = respx.post(PRIMARY).mock(
        return_value=httpx.Response(429, headers={"Retry-After": "20"})
    )
    respx.post(BACKUP).mock(return_value=OK)

    await ask(worker_a.session("run-1"))  # A hits the rate limit
    await ask(worker_b.session("run-2"))  # B skips the cooling provider

    assert primary.call_count == 1
    assert 0 < await redis.pttl("llm:cooldown:primary") <= 20_000
    await redis.aclose()


@respx.mock
async def test_session_reports_the_provider_of_its_last_answer(gateway):
    respx.post(PRIMARY).mock(
        return_value=httpx.Response(429, headers={"Retry-After": "20"})
    )
    respx.post(BACKUP).mock(return_value=OK)
    session = gateway.session("run-1")
    assert session.last_provider is None

    await ask(session)

    assert session.last_provider == "backup"  # who answered, not who was tried first
