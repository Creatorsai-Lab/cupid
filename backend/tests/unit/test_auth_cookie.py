from http.cookies import SimpleCookie

from fastapi import Response

from app.config import settings
from app.routers.auth import COOKIE_KEY, set_auth_cookie


def _auth_cookie_for(app_env: str, monkeypatch) -> SimpleCookie:
    monkeypatch.setattr(settings, "app_env", app_env)
    response = Response()

    set_auth_cookie(response, "test-token")

    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    return cookie


def test_development_auth_cookie_allows_local_http(monkeypatch) -> None:
    cookie = _auth_cookie_for("development", monkeypatch)[COOKIE_KEY]

    assert not cookie["secure"]
    assert cookie["httponly"]
    assert cookie["samesite"] == "lax"
    assert cookie["path"] == "/"


def test_production_auth_cookie_requires_https(monkeypatch) -> None:
    cookie = _auth_cookie_for("production", monkeypatch)[COOKIE_KEY]

    assert cookie["secure"]
    assert cookie["httponly"]
    assert cookie["samesite"] == "lax"
    assert cookie["path"] == "/"
