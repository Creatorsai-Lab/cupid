# defines what keys exist and loads them into Python
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Secret fields use Field(repr=False): printing or logging the settings
    object never shows them (tests/security/test_no_secret_leaks.py)."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid",
        # Validation errors must not echo rejected values: they may be secrets.
        hide_input_in_errors=True,
    )

    # App
    app_env: str = "development"
    secret_key: str = Field(repr=False)
    token_encryption_key: str = Field("", repr=False)
    debug: bool = True
    session_ttl_seconds: int = 60 * 60 * 24 * 7

    # Database
    database_url: str = Field(
        "postgresql+asyncpg://cupid:cupid@localhost:5432/cupid_db", repr=False
    )

    # FRONTEND
    frontend_url: str = "http://localhost:3000"

    # Redis
    # docker-compose.yml maps host 6380 -> container 6379
    redis_url: str = Field("redis://localhost:6380/0", repr=False)

    # External APIs ("" = not configured; a value in .env overrides it)
    groq_api_key: str = Field("", repr=False)
    tavily_api_key: str = Field("", repr=False)  # research agent search (Phase 3)
    gnews_api_key: str = Field("", repr=False)
    # old composer fallback; removed with it (Phase 5)
    huggingface_api_key: str = Field("", repr=False)
    # Google OAuth (for YouTube and other Google services)
    google_client_id: str = ""
    google_client_secret: str = Field("", repr=False)
    google_redirect_uri: str = (
        "http://localhost:8000/api/v1/connections/youtube/callback"
    )
    # Where Google returns the user after the LOGIN consent (distinct from the
    # YouTube-connect callback above). Add this exact URI to the same Google
    # OAuth client's "Authorized redirect URIs".
    google_login_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    # ── Admin ─────────────────────────────────────────────────────────────
    # Emails promoted to is_admin=True automatically at startup (the env
    # allowlist that "designates" admins without touching the DB by hand).
    # In .env: ADMIN_EMAILS=you@gmail.com,partner@x.com
    # NoDecode: stop pydantic-settings from JSON-decoding the env value, so the
    # validator below can accept a plain comma-separated string (a@b.com,c@d.com).
    admin_emails: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # SQLAdmin dashboard — its OWN credential wall, separate from app login.
    # Mounted at admin_panel_path (keep it non-obvious; it is NOT real security
    # on its own, just a thin extra layer over the credential gate).
    admin_panel_path: str = "/ctrl-panel"
    admin_panel_user: str = ""
    admin_panel_password: str = Field("", repr=False)
    # Signs the dashboard's session cookie. Falls back to secret_key if unset.
    admin_session_secret: str = Field("", repr=False)

    @field_validator("admin_emails", mode="before")
    @classmethod
    def _split_admin_emails(cls, v: object) -> object:
        # Accept a comma-separated string from .env (ADMIN_EMAILS=a@b.com,c@d.com)
        # as well as a real list. Normalises to lowercase, trims blanks.
        if isinstance(v, str):
            return [e.strip().lower() for e in v.split(",") if e.strip()]
        return v

    @field_validator("secret_key")
    @classmethod
    def _reject_weak_secret(cls, v: str) -> str:
        banned = {"", "your-secret-key-change-this"}
        # the old committed value — reject it explicitly so it can never come back
        banned.add("Adya2v!gav52bb99+qrva@+$o3v=#tuqyc8=ve$be9=k5#*6#z!gxl")
        if v in banned or len(v) < 32:
            raise ValueError(
                "SECRET_KEY missing or weak. Generate one: "
                'python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        return v


# the single global config object
# This builds the object once, reading env vars + .env
settings = Settings()  # pyright: ignore[reportCallIssue]  # fields come from env/.env
