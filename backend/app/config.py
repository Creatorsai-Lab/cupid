# defines what keys exist and loads them into Python
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid",
    )

    # App
    app_env: str = "development"
    secret_key: str
    token_encryption_key: str = ""
    debug: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://cupid:cupid@localhost:5432/cupid_db"

    # FRONTEND
    FRONTEND_URL: str = "http://localhost:3000"

    # Redis
    # docker-compose.yml maps host 6380 -> container 6379
    redis_url: str = "redis://localhost:6380/0"

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_llm_model: str = "llama3.2"

    # External APIs
    # the "" is only a default fallback. If .env contains ANTHROPIC_API_KEY=..., then Pydantic will override the default.
    tavily_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    huggingface_api_key: str = ""
    gnews_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "cupid/1.0"
    resend_api_key: str = ""
    # Google OAuth (for YouTube and other Google services)
    google_client_id: str = ""
    google_client_secret: str = ""
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
    admin_panel_password: str = ""
    # Signs the dashboard's session cookie. Falls back to secret_key if unset.
    admin_session_secret: str = ""

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
settings = Settings()
