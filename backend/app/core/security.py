from datetime import UTC, datetime, timedelta

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
