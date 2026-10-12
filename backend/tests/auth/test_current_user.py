"""The session cookie decides who the user is; anything doubtful is a 401."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.auth.session import ALGORITHM, COOKIE_KEY, create_access_token
from app.config import settings
from tests.factories import make_user, save

ME = "/api/v1/auth/me"


def cookie(token: str) -> dict[str, str]:
    return {"Cookie": f"{COOKIE_KEY}={token}"}


def token_for(user_id: str, *, key: str | None = None, expires_in: int = 60) -> str:
    payload = {"sub": user_id, "exp": datetime.now(UTC) + timedelta(seconds=expires_in)}
    return jwt.encode(payload, key or settings.secret_key, algorithm=ALGORITHM)


async def test_valid_session_returns_the_user(db_client, db_session):
    user = make_user()
    await save(db_session, user)

    response = await db_client.get(
        ME, headers=cookie(create_access_token(str(user.id)))
    )

    assert response.status_code == 200
    assert response.json()["data"]["email"] == user.email


@pytest.mark.parametrize(
    ("case", "make_token"),
    [
        ("garbage", lambda uid: "not-a-jwt"),
        ("wrong signing key", lambda uid: token_for(uid, key="x" * 64)),
        ("expired", lambda uid: token_for(uid, expires_in=-1)),
        ("unknown user", lambda uid: token_for(str(uuid.uuid4()))),
    ],
)
async def test_doubtful_sessions_are_rejected(db_client, db_session, case, make_token):
    user = make_user()
    await save(db_session, user)

    response = await db_client.get(ME, headers=cookie(make_token(str(user.id))))

    assert response.status_code == 401, case


async def test_disabled_account_is_rejected(db_client, db_session):
    user = make_user(is_active=False)
    await save(db_session, user)

    response = await db_client.get(
        ME, headers=cookie(create_access_token(str(user.id)))
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Account is disabled"
