"""Login history: the client IP behind our proxy, recording sign-ins, and the
Settings endpoint that lists them."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import fakeredis
import pytest
from httpx import AsyncClient
from starlette.requests import Request

from app.auth import otp
from app.auth.models import LoginEvent
from app.core import client_ip as client_ip_module
from app.core.client_ip import client_ip
from app.core.redis import get_redis
from app.main import app
from tests.factories import make_user, save

PHONE = "919999999999"


def make_request(peer: str, forwarded: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


# ── client_ip ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("hops", "forwarded", "expected"),
    [
        (1, None, "10.0.0.2"),  # no proxy header: the socket address
        (1, "203.0.113.7", "203.0.113.7"),
        (1, "6.6.6.6, 203.0.113.7", "203.0.113.7"),  # forged left entry ignored
        (2, "6.6.6.6, 203.0.113.7, 172.68.1.1", "203.0.113.7"),  # CDN + Traefik
        (2, "203.0.113.7", "203.0.113.7"),  # shorter chain than proxies
        (0, "6.6.6.6", "10.0.0.2"),  # header not trusted at all
    ],
)
def test_client_ip_takes_the_entry_our_proxy_added(
    monkeypatch, hops: int, forwarded: str | None, expected: str
):
    monkeypatch.setattr(client_ip_module.settings, "trusted_proxy_count", hops)
    assert client_ip(make_request("10.0.0.2", forwarded)) == expected


# ── Recording + listing ───────────────────────────────────────


async def test_phone_login_is_recorded_with_client_ip(
    db_client: AsyncClient, db_session, monkeypatch, sign_in
):
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: redis
    monkeypatch.setattr(otp.settings, "apitxt_authkey", "test-key")
    sent: list[str] = []

    async def fake_sms(phone: str, code: str) -> None:
        sent.append(code)

    monkeypatch.setattr(otp, "send_otp_sms", fake_sms)
    monkeypatch.setattr(client_ip_module.settings, "trusted_proxy_count", 1)
    user = make_user(email=None, phone=PHONE)
    await save(db_session, user)
    await otp.send_code(redis, PHONE, "1.1.1.1")

    resp = await db_client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": PHONE, "code": sent[0]},
        headers={"x-forwarded-for": "203.0.113.7", "user-agent": "TestBrowser/1.0"},
    )
    assert resp.status_code == 200

    sign_in(user)
    history = await db_client.get("/api/v1/auth/login-history")
    assert history.status_code == 200
    (event,) = history.json()["data"]
    assert event["method"] == "phone"
    assert event["ip_address"] == "203.0.113.7"
    assert event["user_agent"] == "TestBrowser/1.0"


async def test_history_is_own_logins_newest_first(
    db_client: AsyncClient, db_session, sign_in
):
    me, other = make_user(), make_user()
    now = datetime.now(UTC)
    await save(
        db_session,
        me,
        other,
        LoginEvent(
            user_id=me.id,
            method="google",
            ip_address="1.1.1.1",
            created_at=now - timedelta(days=1),
        ),
        LoginEvent(user_id=me.id, method="phone", ip_address="2.2.2.2", created_at=now),
        LoginEvent(user_id=other.id, method="google", ip_address="9.9.9.9"),
    )
    sign_in(me)

    resp = await db_client.get("/api/v1/auth/login-history")

    assert [e["ip_address"] for e in resp.json()["data"]] == ["2.2.2.2", "1.1.1.1"]
