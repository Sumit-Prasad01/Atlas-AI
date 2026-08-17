"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings shared by the backend application and its workers."""

    app_name: str = "Atlas AI API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    host: str = "127.0.0.1"
    port: int = 8000
    database_echo: bool = False
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # These are optional until the database and service integrations are added.
    database_url: str | None = None
    redis_url: str | None = None
    redis_connect_timeout_seconds: float = 1.0
    redis_socket_timeout_seconds: float = 1.0
    qdrant_url: str | None = None
    minio_endpoint: str | None = None

    # Cloud model providers. Set the key/token for the provider in use.
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    huggingfacehub_api_token: str | None = None
    huggingface_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings object for the process."""

    return Settings()
