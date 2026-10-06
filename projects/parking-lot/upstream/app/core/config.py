"""Application configuration via environment variables."""

from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SECRET_KEY = "change-me-in-production-use-a-32-byte-secret-minimum"
_MIN_SECRET_BYTES = 32
_INSECURE_ALLOWED_ENVIRONMENTS = frozenset({"development", "test"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Parking Management API"
    api_prefix: str = "/api"
    # Secure by default: anything other than development/test enforces a
    # strong SECRET_KEY at startup.
    environment: str = "production"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/parking"
    secret_key: str = PLACEHOLDER_SECRET_KEY
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    evidence_storage_path: str = "./data/evidence"
    evidence_max_bytes: int = 5 * 1024 * 1024
    evidence_max_files: int = 5
    # IANA zone used for billing day boundaries, night windows and reports.
    business_timezone: str = "America/Bogota"
    # Comma-separated explicit origins (Flutter web dev, e.g.
    # "http://localhost:5000"). Empty = no cross-origin browser access;
    # native mobile clients do not need CORS.
    cors_origins: str = ""
    # Optional shared cache / login limiter (e.g. "redis://redis:6379/0").
    # Unset = in-process implementations (fine for a single worker).
    redis_url: str | None = None
    # "json" writes one JSON object per log line (to LOG_FILE, else stdout).
    log_format: str = "text"
    log_file: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def business_zone(self) -> ZoneInfo:
        return ZoneInfo(self.business_timezone)

    @field_validator("business_timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown timezone: {value}") from exc
        return value

    @model_validator(mode="after")
    def _strong_secret_outside_dev(self) -> Self:
        if self.environment in _INSECURE_ALLOWED_ENVIRONMENTS:
            return self
        weak = len(self.secret_key.encode()) < _MIN_SECRET_BYTES
        if weak or self.secret_key == PLACEHOLDER_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY must be set to a random value of at least 32 bytes "
                f"when ENVIRONMENT={self.environment!r}"
            )
        return self


settings = Settings()
