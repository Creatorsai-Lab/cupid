from http.cookies import SimpleCookie
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.models.user import User
from app.routers import oauth_google
from app.routers.auth import COOKIE_KEY


def mock_successful_google_response(monkeypatch, user: User):
    consume_state = AsyncMock(return_value=True)
    exchange_code = AsyncMock(return_value={"access_token": "google-access-token"})
    fetch_userinfo = AsyncMock(
        return_value={
            "sub": "google-account-123",
            "email": user.email,
            "email_verified": True,
            "name": "Google Creator",
            "picture": "https://example.com/avatar.png",
        }
    )
    find_user = AsyncMock(return_value=user)

    monkeypatch.setattr(oauth_google, "consume_login_state", consume_state)
    monkeypatch.setattr(oauth_google, "exchange_code", exchange_code)
    monkeypatch.setattr(oauth_google, "fetch_userinfo", fetch_userinfo)
    monkeypatch.setattr(oauth_google, "get_user_by_email", find_user)

    return consume_state, exchange_code, fetch_userinfo, find_user


@pytest.mark.asyncio
async def test_callback_links_active_user_and_sets_cookie(monkeypatch) -> None:
    user = User(
        id=uuid4(),
        full_name="Legacy Creator",
        email="creator@example.com",
        hashed_password="legacy-password-hash",
        auth_provider="password",
        is_active=True,
    )
    db = AsyncMock()

    consume_state, exchange_code, fetch_userinfo, find_user = (
        mock_successful_google_response(monkeypatch, user)
    )

    create_token = Mock(return_value="test-session-token")
    monkeypatch.setattr(oauth_google, "create_access_token", create_token)
    monkeypatch.setattr(
        oauth_google.settings,
        "frontend_url",
        "http://frontend.test",
    )

    response = await oauth_google.google_callback(
        code="google-code",
        state="valid-state",
        error=None,
        redis=object(),
        db=db,
    )

    assert response.status_code == 307
    assert response.headers["location"] == (
        "http://frontend.test/complete?next=/create"
    )

    cookies = SimpleCookie()
    cookies.load(response.headers["set-cookie"])

    assert cookies[COOKIE_KEY].value == "test-session-token"
    assert user.auth_provider == "google"
    assert user.provider_account_id == "google-account-123"
    assert user.hashed_password is None

    consume_state.assert_awaited_once()
    exchange_code.assert_awaited_once_with("google-code")
    fetch_userinfo.assert_awaited_once_with("google-access-token")
    find_user.assert_awaited_once_with(db, "creator@example.com")
    create_token.assert_called_once_with(str(user.id))
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_callback_rejects_disabled_user_without_cookie(monkeypatch) -> None:
    user = User(
        id=uuid4(),
        full_name="Disabled Creator",
        email="disabled@example.com",
        hashed_password=None,
        auth_provider="google",
        provider_account_id="google-account-123",
        is_active=False,
    )
    db = AsyncMock()

    mock_successful_google_response(monkeypatch, user)

    create_token = Mock(return_value="must-not-be-issued")
    link_identity = Mock()

    monkeypatch.setattr(oauth_google, "create_access_token", create_token)
    monkeypatch.setattr(oauth_google, "link_google_identity", link_identity)
    monkeypatch.setattr(
        oauth_google.settings,
        "frontend_url",
        "http://frontend.test",
    )

    response = await oauth_google.google_callback(
        code="google-code",
        state="valid-state",
        error=None,
        redis=object(),
        db=db,
    )

    assert response.status_code == 307
    assert response.headers["location"] == (
        "http://frontend.test/signin?error=disabled"
    )
    assert "set-cookie" not in response.headers

    create_token.assert_not_called()
    link_identity.assert_not_called()
    db.commit.assert_not_awaited()
    db.refresh.assert_not_awaited()
