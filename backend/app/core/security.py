"""
Security utilities: password hashing and JWT management.

This module handles the two core security operations:
1. Password hashing (bcrypt) — for storing passwords safely
2. JWT tokens — for authenticating subsequent requests

Note: We use bcrypt directly instead of passlib because passlib
is unmaintained and has compatibility issues with bcrypt 4.1+.
This is the approach used by FastAPI's own documentation now.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import settings

# ── Password Hashing ─────────────────────────────────────────


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.
    
    How it works:
    1. bcrypt.gensalt() creates a random salt (prevents identical
       passwords from producing identical hashes)
    2. bcrypt.hashpw() combines salt + password → 60-char hash
    3. We decode to str because our DB column is String, not bytes
    """
    salt = bcrypt.gensalt(rounds=12)  # 12 rounds = ~250ms per hash (good balance)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Check if a plain-text password matches a stored hash.
    
    bcrypt.checkpw handles salt extraction automatically —
    the salt is embedded in the first 29 characters of the hash.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ── JWT Tokens ────────────────────────────────────────────────

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_token(user_id: str) -> str:
    """Create a JWT containing the user's ID."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
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
