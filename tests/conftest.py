import pytest

from intelligent_marketplace.core.config import Settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def app_settings():
    # Explicit settings keep HTTP tests independent of the developer's local .env.
    return Settings(
        _env_file=None,
        app_name="Intelligent Marketplace API",
        app_env="test",
        docs_enabled=True,
        database_url=None,
        database_connect_timeout_seconds=5,
    )
