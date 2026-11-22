"""Configuração validada a partir do ambiente e de um arquivo .env opcional."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Intelligent Marketplace API", min_length=1)
    app_env: Literal["development", "test", "production"] = "development"
    docs_enabled: bool = True
