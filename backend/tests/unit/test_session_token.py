from datetime import UTC, datetime

from jose import jwt

from app.config import settings
from app.core.security import ALGORITHM, create_access_token


def test_access_token_uses_configured_session_lifetime(monkeypatch) -> None:
    monkeypatch.setattr(settings, "session_ttl_seconds", 600)

    before = int(datetime.now(UTC).timestamp())
    token = create_access_token("user-123")
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    after = int(datetime.now(UTC).timestamp())

    assert before + 600 <= payload["exp"] <= after + 600
