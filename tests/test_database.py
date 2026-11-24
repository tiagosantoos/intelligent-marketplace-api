from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import Depends
from sqlalchemy.exc import OperationalError

from intelligent_marketplace.core.config import Settings
from intelligent_marketplace.infrastructure.database import (
    Database,
    DatabaseNotConfiguredError,
    get_database,
    get_session,
)
from intelligent_marketplace.main import create_app


def test_database_url_is_optional_and_secret():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:example-secret@localhost:5432/marketplace",
    )
    assert "example-secret" not in repr(settings)
    assert Settings(_env_file=None, database_url="").database_url is None


@pytest.mark.parametrize(
    "url",
    ["invalid", "sqlite:///local.db", "postgresql+asyncpg://user:pass@localhost/db"],
)
def test_unsupported_database_urls_are_rejected(url):
    with pytest.raises(ValueError):
        Settings(_env_file=None, database_url=url)


def test_unconfigured_database_does_not_connect(app_settings):
    database = Database(app_settings)
    with pytest.raises(DatabaseNotConfiguredError):
        database.check_connection()
    database.dispose()


def test_connection_uses_read_only_probe_and_releases_connection(app_settings):
    database = Database(app_settings)
    database.engine = MagicMock()
    connection = database.engine.connect.return_value.__enter__.return_value

    database.check_connection()

    assert str(connection.execute.call_args.args[0]) == "SELECT 1"
    database.engine.connect.return_value.__exit__.assert_called_once()


def test_session_closes_on_failure_without_implicit_commit(app_settings):
    database = Database(app_settings)
    database.session_factory = MagicMock()
    session = database.session_factory.return_value.__enter__.return_value
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(database=database)))
    iterator = get_session(request)
    assert next(iterator) is session

    with pytest.raises(RuntimeError, match="service failed"):
        iterator.throw(RuntimeError("service failed"))

    database.session_factory.return_value.__exit__.assert_called_once()
    session.commit.assert_not_called()


@pytest.mark.anyio
async def test_readiness_without_database_and_liveness(app_settings):
    app = create_app(app_settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database is not configured"}
        assert (await client.get("/health")).status_code == 200


@pytest.mark.anyio
async def test_readiness_with_available_database(app_settings):
    app = create_app(app_settings)
    database = MagicMock()
    app.dependency_overrides[get_database] = lambda: database
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}
    database.check_connection.assert_called_once()


@pytest.mark.anyio
async def test_readiness_hides_driver_details(app_settings):
    app = create_app(app_settings)
    database = MagicMock()
    database.check_connection.side_effect = OperationalError(
        "SELECT 1", None, Exception("user:example-secret@internal-host")
    )
    app.dependency_overrides[get_database] = lambda: database
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}
    assert "example-secret" not in response.text


@pytest.mark.anyio
async def test_session_dependency_returns_503_when_not_configured(app_settings):
    app = create_app(app_settings)

    @app.get("/test-session")
    def route(session=Depends(get_session)):
        return {"unexpected": True}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/test-session")).status_code == 503


@pytest.mark.anyio
async def test_application_disposes_database_on_shutdown(app_settings):
    app = create_app(app_settings)
    app.state.database.dispose = MagicMock()
    async with app.router.lifespan_context(app):
        pass
    app.state.database.dispose.assert_called_once()
