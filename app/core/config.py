"""Centralised runtime configuration via environment (and optional ``.env``)."""

import logging
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    database_url: str = Field(
        ...,
        description="PostgreSQL connection URL (Supabase pooler or direct).",
        validation_alias="DATABASE_URL",
    )
    log_level: str = Field(
        default="INFO",
        description="Root logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
        validation_alias="LOG_LEVEL",
    )
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable slowapi limits (disable for local pytest unless you tune limits).",
        validation_alias="RATE_LIMIT_ENABLED",
    )
    rate_limit_default: str = Field(
        default="200/minute",
        description="Default quota for endpoints that expose ``Request`` to slowapi.",
        validation_alias="RATE_LIMIT_DEFAULT",
    )
    rate_limit_write: str = Field(
        default="45/minute",
        description="Quota for POST /users and POST /users/register.",
        validation_alias="RATE_LIMIT_WRITE_POST",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def strip_database_url(cls, value: object) -> object:
        # Secret Manager or copy-paste often leaves trailing newlines.
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("log_level", mode="after")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.strip().upper()

    def resolved_log_level(self) -> int:
        """Numeric level for ``logging`` (unknown names fall back to INFO)."""
        mapping = logging.getLevelNamesMapping()
        return mapping.get(self.log_level, logging.INFO)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached ``Settings`` instance."""
    return Settings()
