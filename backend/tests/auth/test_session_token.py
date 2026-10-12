from datetime import UTC, datetime

import jwt

from app.auth.session import ALGORITHM, create_access_token
from app.config import settings


def test_access_token_uses_configured_session_lifetime(monkeypatch) -> None:
    monkeypatch.setattr(settings, "session_ttl_seconds", 600)

    before = int(datetime.now(UTC).timestamp())
    token = create_access_token("user-123")
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    after = int(datetime.now(UTC).timestamp())

    assert before + 600 <= payload["exp"] <= after + 600


# Signed by python-jose (the previous JWT library) with a fixed test key. Sessions
# issued before the switch to PyJWT must stay valid, so PyJWT must decode it.
JOSE_ISSUED_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiI2ZjFjMmI3ZS0wMDAwLTQwMDAtODAwMC0wMDAwMDAwMDAwMDEiLCJleHAiOjQwNzA5MDg4MDB9."
    "MESKd6rPN_VfCxfHn2ZuMwjQLNsjOr-H6yvgwIxEqVc"
)


def test_tokens_issued_by_the_previous_library_still_decode() -> None:
    payload = jwt.decode(
        JOSE_ISSUED_TOKEN,
        "compat-test-key-not-a-secret-0123456789",
        algorithms=[ALGORITHM],
    )
    assert payload["sub"] == "6f1c2b7e-0000-4000-8000-000000000001"
