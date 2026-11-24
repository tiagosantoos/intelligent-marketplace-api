"""Configuração validada a partir do ambiente e de um arquivo .env opcional."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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
    openai_api_key: SecretStr | None = None
    openai_model: str | None = None
    agent_timeout_seconds: int = Field(default=60, ge=1, le=120)
    api_access_key: SecretStr | None = Field(default=None, min_length=32, max_length=256)
    executive_requests_per_minute: int = Field(default=6, ge=1, le=60)
    executive_max_concurrent: int = Field(default=1, ge=1, le=5)

    @field_validator("openai_api_key", "openai_model", "api_access_key", mode="before")
    @classmethod
    def empty_openai_setting(cls, value):
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        return None if raw is None or not raw.strip() else raw.strip()

    @model_validator(mode="after")
    def require_public_access_key(self):
        if self.app_env == "production" and self.api_access_key is None:
            raise ValueError("API_ACCESS_KEY is required in production")
        if self.api_access_key is not None and self.openai_api_key is not None:
            if self.api_access_key.get_secret_value() == self.openai_api_key.get_secret_value():
                raise ValueError("API_ACCESS_KEY must differ from OPENAI_API_KEY")
        return self

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
