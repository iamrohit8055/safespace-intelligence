"""Application configuration management using Pydantic Settings."""

import json
from functools import lru_cache
from typing import Any, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration loaded from environment variables and .env files."""

    # Application Metadata
    APP_NAME: str = "SafeSpace Intelligence"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"  # development, staging, production, testing
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Database Configuration
    DATABASE_URL: str = (
        "postgresql+psycopg://safespace_user:safespace_password@127.0.0.1:5433/safespace_db"
    )
    DATABASE_POOL_TYPE: str = (
        "queue"  # "queue" for persistent servers, "null" for serverless (Vercel)
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_RECYCLE_SECONDS: int = 3600

    # Security & Tokens
    # Development placeholder: production environments must provide a securely generated secret.
    SECRET_KEY: str = "development_secret_key_change_in_production_min_32_chars"
    JWT_SECRET_KEY: str = "development_secret_key_change_in_production_min_32_chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Media Object Storage
    MEDIA_STORAGE_PATH: str = "uploads/media"
    MEDIA_STORAGE_BUCKET: str = "safespace-media-local"
    MEDIA_STORAGE_PROVIDER: str = "local"

    # Cross-Origin Resource Sharing
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://[::1]:5173",
        "http://[::1]:8000",
    ]

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, value: Any) -> list[str]:
        """Parse CORS origins from a list, JSON string, or comma-separated string."""
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(origin).strip() for origin in parsed]
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(origin).strip() for origin in value]
        return []

    @model_validator(mode="after")
    def validate_security_configuration(self) -> Self:
        """Ensure production environments supply securely generated secrets."""
        if self.is_production:
            insecure_defaults = {
                "development_secret_key_change_in_production_min_32_chars",
                "secret",
                "changeme",
                "password",
            }
            if self.JWT_SECRET_KEY in insecure_defaults or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must be a securely generated secret "
                    "with at least 32 characters in production."
                )
            if self.SECRET_KEY in insecure_defaults or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "SECRET_KEY must be a securely generated secret "
                    "with at least 32 characters in production."
                )
        return self

    @property
    def is_production(self) -> bool:
        """Return True if running in production mode."""
        return self.APP_ENV.lower() == "production"

    @property
    def is_testing(self) -> bool:
        """Return True if running in testing mode."""
        return self.APP_ENV.lower() == "testing"


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
