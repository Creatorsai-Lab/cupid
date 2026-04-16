# defines what keys exist and loads them into Python


from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", # read backend/.env
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid",
    )

    # App
    app_env: str = "development"
    secret_key: str = "Adya2v!gav52bb99+qrva@+$o3v=#tuqyc8=ve$be9=k5#*6#z!gxl"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://cupid:cupid@localhost:5432/cupid_db"

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
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "cupid/1.0"
    resend_api_key: str = ""

# the single global config object
# This builds the object once, reading env vars + .env
settings = Settings()