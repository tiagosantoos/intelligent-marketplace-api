"""Configuração validada a partir do ambiente e de um arquivo .env opcional."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_name: str = Field(default="Intelligent Marketplace API", min_length=1)
    app_env: Literal["development", "test", "production"] = "development"
    docs_enabled: bool = True
    database_url: SecretStr | None = None
    database_connect_timeout_seconds: int = Field(default=5, ge=1, le=30)
    analytics_query_timeout_seconds: int = Field(default=5, ge=1, le=30)

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, value):
        if value is None or value == "":
            return None
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        try:
            url = make_url(raw)
            if url.drivername != "postgresql+psycopg" or not url.host or not url.database:
                raise ValueError
        except (ArgumentError, TypeError, ValueError):
            raise ValueError(
                "DATABASE_URL must use postgresql+psycopg:// with a host and database"
            ) from None
        return value
