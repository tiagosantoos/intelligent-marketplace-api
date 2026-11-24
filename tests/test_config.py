import httpx
import pytest
from pydantic import ValidationError

from intelligent_marketplace.core.config import Settings
from intelligent_marketplace.main import create_app


@pytest.fixture(autouse=True)
def clear_settings_environment(monkeypatch):
    for name in (
        "APP_NAME", "APP_ENV", "DOCS_ENABLED", "DATABASE_URL",
        "DATABASE_CONNECT_TIMEOUT_SECONDS",
        "API_ACCESS_KEY", "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults_work_without_env_file():
    settings = Settings(_env_file=None)

    assert settings.app_name == "Intelligent Marketplace API"
    assert settings.app_env == "development"
    assert settings.docs_enabled is True
    assert settings.database_url is None


def test_environment_overrides_dotenv(tmp_path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        'APP_NAME="Local Marketplace"\nAPP_ENV=development\nDOCS_ENABLED=false\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("API_ACCESS_KEY", "a" * 32)

    settings = Settings(_env_file=dotenv)

    assert settings.app_name == "Local Marketplace"
    assert settings.app_env == "production"
    assert settings.docs_enabled is False


@pytest.mark.parametrize(
    ("name", "value"),
    [("APP_ENV", "invalid"), ("DOCS_ENABLED", "invalid"), ("APP_NAME", "")],
)
def test_invalid_environment_fails_validation(name, value, monkeypatch):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.anyio
async def test_custom_title_and_disabled_docs_keep_health_available():
    settings = Settings(
        _env_file=None,
        app_name="Configured API",
        app_env="test",
        docs_enabled=False,
        database_url=None,
    )
    app = create_app(settings)

    assert app.title == "Configured API"
    assert app.state.settings.app_env == "test"

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert (await client.get(path)).status_code == 404
        assert (await client.get("/health")).json() == {"status": "ok"}
