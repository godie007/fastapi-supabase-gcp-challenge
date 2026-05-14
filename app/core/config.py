"""Centralised runtime configuration via environment (and optional ``.env``)."""

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

    @field_validator("database_url", mode="before")
    @classmethod
    def strip_database_url(cls, value: object) -> object:
        # Secret Manager or copy-paste often leaves trailing newlines.
        if isinstance(value, str):
            return value.strip()
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached ``Settings`` instance."""
    return Settings()
