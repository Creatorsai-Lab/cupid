"""Phone OTP login: code storage, rate limits, the APITxT client, and the routes."""

from __future__ import annotations

import json
from http.cookies import SimpleCookie
from unittest.mock import AsyncMock

import fakeredis
import httpx
import pytest
from fastapi import Response
from httpx import AsyncClient

from app.auth import apitxt, otp
from app.auth import router as auth_router
from app.auth.apitxt import SmsSendError
from app.auth.session import COOKIE_KEY
from app.core.errors import ServiceUnavailableError
from app.core.redis import get_redis
from app.main import app
from tests.factories import make_user, save

PHONE = "919999999999"


@pytest.fixture
def redis():
    return fakeredis.FakeAsyncRedis(decode_responses=True)


@pytest.fixture
def sms(monkeypatch) -> AsyncMock:
    """Capture outgoing SMS instead of calling APITxT."""
    monkeypatch.setattr(otp.settings, "apitxt_authkey", "test-key")
    send = AsyncMock()
    monkeypatch.setattr(otp, "send_otp_sms", send)
    return send


def sent_code(sms: AsyncMock) -> str:
    assert sms.await_args is not None, "no SMS was sent"
    return sms.await_args.args[1]


# ── normalize_phone ───────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("9999999999", "919999999999"),
        ("+91 99999-99999", "919999999999"),
        ("919999999999", "919999999999"),
        ("+1 (415) 555-1234", "14155551234"),
    ],
)
def test_normalize_phone_accepts_common_formats(raw: str, expected: str):
    assert otp.normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["99999abcde", "123456789", "09999999999", "1" * 16])
def test_normalize_phone_rejects_bad_numbers(raw: str):
    with pytest.raises(otp.InvalidPhoneError):
        otp.normalize_phone(raw)


# ── send_code ─────────────────────────────────────────────────


async def test_send_stores_only_a_hash_of_the_code(redis, sms):
    await otp.send_code(redis, PHONE, "1.1.1.1")

    code = sent_code(sms)
    stored = await redis.hgetall(f"{otp.CODE_KEY}{PHONE}")
    assert len(code) == 6 and code.isdigit()
    assert code not in json.dumps(stored)
    assert 0 < await redis.ttl(f"{otp.CODE_KEY}{PHONE}") <= otp.CODE_TTL_SECONDS


async def test_send_refuses_without_authkey(redis, monkeypatch):
    monkeypatch.setattr(otp.settings, "apitxt_authkey", "")
    with pytest.raises(ServiceUnavailableError):
        await otp.send_code(redis, PHONE, "1.1.1.1")


async def test_second_send_within_cooldown_is_rate_limited(redis, sms):
    await otp.send_code(redis, PHONE, "1.1.1.1")
    with pytest.raises(otp.RateLimitedError):
        await otp.send_code(redis, PHONE, "1.1.1.1")
    assert sms.await_count == 1


async def test_sends_per_phone_are_capped_per_hour(redis, sms):
    for _ in range(otp.SENDS_PER_PHONE_PER_HOUR):
        await otp.send_code(redis, PHONE, "1.1.1.1")
        await redis.delete(f"{otp.COOLDOWN_KEY}{PHONE}")  # skip the 60s wait

    with pytest.raises(otp.RateLimitedError):
        await otp.send_code(redis, PHONE, "1.1.1.1")


async def test_sends_per_ip_are_capped_per_hour(redis, sms):
    for i in range(otp.SENDS_PER_IP_PER_HOUR):
        await otp.send_code(redis, f"9199999{i:05d}", "6.6.6.6")

    with pytest.raises(otp.RateLimitedError):
        await otp.send_code(redis, "918888888888", "6.6.6.6")


async def test_failed_sms_drops_code_and_allows_retry(redis, sms):
    sms.side_effect = SmsSendError("rejected")
    with pytest.raises(otp.SmsDeliveryError):
        await otp.send_code(redis, PHONE, "1.1.1.1")

    assert not await redis.exists(f"{otp.CODE_KEY}{PHONE}")
    sms.side_effect = None
    await otp.send_code(redis, PHONE, "1.1.1.1")  # no cooldown left behind


# ── verify_code ───────────────────────────────────────────────


async def test_correct_code_verifies_once(redis, sms):
    await otp.send_code(redis, PHONE, "1.1.1.1")
    code = sent_code(sms)

    await otp.verify_code(redis, PHONE, code)
    with pytest.raises(otp.InvalidCodeError):
        await otp.verify_code(redis, PHONE, code)


async def test_wrong_code_is_rejected(redis, sms):
    await otp.send_code(redis, PHONE, "1.1.1.1")
    wrong = f"{(int(sent_code(sms)) + 1) % 10**6:06d}"
    with pytest.raises(otp.InvalidCodeError):
        await otp.verify_code(redis, PHONE, wrong)


async def test_code_dies_after_max_attempts(redis, sms):
    await otp.send_code(redis, PHONE, "1.1.1.1")
    code = sent_code(sms)
    wrong = f"{(int(code) + 1) % 10**6:06d}"
    for _ in range(otp.MAX_ATTEMPTS):
        with pytest.raises(otp.InvalidCodeError):
            await otp.verify_code(redis, PHONE, wrong)

    with pytest.raises(otp.InvalidCodeError, match="Too many"):
        await otp.verify_code(redis, PHONE, code)
    assert not await redis.exists(f"{otp.CODE_KEY}{PHONE}")


async def test_verify_without_send_leaves_no_key(redis):
    with pytest.raises(otp.InvalidCodeError):
        await otp.verify_code(redis, PHONE, "123456")
    assert not await redis.exists(f"{otp.CODE_KEY}{PHONE}")


# ── APITxT client ─────────────────────────────────────────────


def mock_apitxt(monkeypatch, status: int, body: dict) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=body)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        apitxt.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    monkeypatch.setattr(apitxt.settings, "apitxt_authkey", "secret-key")
    monkeypatch.setattr(apitxt.settings, "apitxt_sms_template_id", "42")
    return seen


async def test_client_posts_key_in_body_not_url(monkeypatch):
    seen = mock_apitxt(monkeypatch, 200, {"status": "success", "data": {}})

    await apitxt.send_otp_sms(PHONE, "123456")

    (req,) = seen
    assert req.method == "POST"
    assert req.url.path == "/api/sendOTP"
    assert "secret-key" not in str(req.url)
    form = dict(httpx.QueryParams(req.content.decode()))
    assert form == {
        "authkey": "secret-key",
        "mobile": PHONE,
        "otp": "123456",
        "template_id": "42",
    }


async def test_client_raises_when_apitxt_rejects(monkeypatch):
    mock_apitxt(
        monkeypatch, 200, {"status": "error", "code": 301, "message": "Low balance"}
    )
    with pytest.raises(SmsSendError, match="301"):
        await apitxt.send_otp_sms(PHONE, "123456")


# ── Routes ────────────────────────────────────────────────────


async def test_send_route_returns_timings(client: AsyncClient, redis, sms):
    app.dependency_overrides[get_redis] = lambda: redis

    resp = await client.post("/api/v1/auth/otp/send", json={"phone": "9999999999"})

    assert resp.status_code == 200
    assert resp.json()["data"] == {
        "expires_in": otp.CODE_TTL_SECONDS,
        "resend_in": otp.RESEND_COOLDOWN_SECONDS,
    }
    assert sms.await_args.args[0] == PHONE


async def test_send_route_rejects_bad_phone(client: AsyncClient, redis, sms):
    app.dependency_overrides[get_redis] = lambda: redis

    resp = await client.post("/api/v1/auth/otp/send", json={"phone": "abcdefghijk"})

    assert resp.status_code == 422
    sms.assert_not_awaited()


async def test_verify_route_rejects_wrong_code_without_cookie(redis, sms, monkeypatch):
    await otp.send_code(redis, PHONE, "1.1.1.1")
    find_user = AsyncMock()
    monkeypatch.setattr(auth_router, "get_user_by_phone", find_user)
    response = Response()

    with pytest.raises(otp.InvalidCodeError):
        await auth_router.otp_verify(
            body=auth_router.OtpVerifyRequest(phone=PHONE, code="000000"),
            response=response,
            redis=redis,
            db=AsyncMock(),
        )
    find_user.assert_not_awaited()
    assert "set-cookie" not in response.headers


async def test_verify_creates_new_user_and_sets_cookie(db_client, redis, sms):
    app.dependency_overrides[get_redis] = lambda: redis
    await db_client.post("/api/v1/auth/otp/send", json={"phone": "9999999999"})

    resp = await db_client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": "+91 99999 99999", "code": sent_code(sms)},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["next"] == "/settings"
    assert body["data"]["phone"] == PHONE
    assert body["data"]["email"] is None
    cookies = SimpleCookie()
    cookies.load(resp.headers["set-cookie"])
    assert cookies[COOKIE_KEY].value


async def test_verify_logs_in_existing_user(db_client, db_session, redis, sms):
    app.dependency_overrides[get_redis] = lambda: redis
    user = make_user(email=None, phone=PHONE)
    await save(db_session, user)
    await otp.send_code(redis, PHONE, "1.1.1.1")

    resp = await db_client.post(
        "/api/v1/auth/otp/verify", json={"phone": PHONE, "code": sent_code(sms)}
    )

    assert resp.status_code == 200
    assert resp.json()["next"] == "/create"
    assert resp.json()["data"]["id"] == str(user.id)


async def test_verify_refuses_disabled_user(db_client, db_session, redis, sms):
    app.dependency_overrides[get_redis] = lambda: redis
    await save(db_session, make_user(phone=PHONE, is_active=False))
    await otp.send_code(redis, PHONE, "1.1.1.1")

    resp = await db_client.post(
        "/api/v1/auth/otp/verify", json={"phone": PHONE, "code": sent_code(sms)}
    )

    assert resp.status_code == 403
    assert "set-cookie" not in resp.headers
