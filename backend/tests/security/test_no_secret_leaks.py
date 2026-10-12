"""Secrets must not leak through settings output, validation errors or 500 responses.

The settings case is real: on 2026-10-09 a settings validation error printed
truncated API keys, because pydantic echoes the rejected input by default.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app

SECRET = "LEAK-CANARY-7f3a9c"  # any output containing this has leaked a secret
VALID_KEY = "k" * 40 + SECRET


def settings_without_env_file(**values) -> Settings:
    return Settings(_env_file=None, **values)


def test_settings_repr_hides_secret_values():
    settings = settings_without_env_file(
        secret_key=VALID_KEY,
        token_encryption_key=SECRET,
        google_client_secret=SECRET,
        groq_api_key=SECRET,
        tavily_api_key=SECRET,
        gnews_api_key=SECRET,
        huggingface_api_key=SECRET,
        admin_panel_password=SECRET,
        admin_session_secret=SECRET,
        database_url=f"postgresql+asyncpg://cupid:{SECRET}@localhost/db",
        redis_url=f"redis://:{SECRET}@localhost:6379/0",
    )
    assert SECRET not in repr(settings)
    assert SECRET not in str(settings)


@pytest.mark.parametrize(
    "bad_values",
    [
        {"secret_key": f"short-{SECRET}"},  # rejected: too short
        {"secret_key": VALID_KEY, "gemini_api_key": SECRET},  # rejected: unknown key
    ],
    ids=["rejected value", "unknown key"],
)
def test_settings_errors_do_not_echo_input(bad_values):
    with pytest.raises(ValidationError) as error:
        settings_without_env_file(**bad_values)
    assert SECRET not in str(error.value)


async def test_unhandled_errors_do_not_reveal_details():
    app = create_app()

    @app.get("/explode")
    async def explode():
        raise RuntimeError(f"db password is {SECRET}")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/explode")

    assert response.status_code == 500
    assert SECRET not in response.text
