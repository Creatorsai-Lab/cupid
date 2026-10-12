"""Session: the signed JWT and the HTTP-only cookie that carries it."""

from datetime import UTC, datetime, timedelta

from fastapi import Response
from jose import JWTError, jwt

from app.config import settings

# ── JWT Tokens ────────────────────────────────────────────────

ALGORITHM = "HS256"


def create_access_token(user_id: str) -> str:
    """Create a JWT containing the user's ID."""
    expire = datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds)
    payload = {
        "sub": user_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Decode and verify a JWT. Returns user_id if valid, None if invalid/expired."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        return user_id
    except JWTError:
        return None


# ── Session cookie ────────────────────────────────────────────

COOKIE_KEY = "cupid_access_token"


def set_auth_cookie(response: Response, token: str) -> None:
    """
    Set the JWT as an HTTP-only cookie.

    httponly=True   → JS can't read it (XSS protection)
    secure          → allows local HTTP in development; requires HTTPS in production
    samesite="lax"  → cookie sent on same-site requests + top-level navigations
                      "strict" would break OAuth redirects
    """
    response.set_cookie(
        key=COOKIE_KEY,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/",
    )
