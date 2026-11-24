import asyncio

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from intelligent_marketplace.api import executive, security
from intelligent_marketplace.core.config import Settings
from intelligent_marketplace.main import create_app
from intelligent_marketplace.agents.executive.assistant import ExecutiveAnswer

KEY = "test-access-key-not-a-real-secret-123456"
HEADERS = {"X-API-Key": KEY}


def protected_app(**overrides):
    return create_app(Settings(_env_file=None, database_url=None, openai_api_key=None, app_env="production", api_access_key=KEY, **overrides))


async def answer(*args):
    return ExecutiveAnswer(answer="Teste local", evidence=[], model="fake")


def test_production_requires_distinct_secret_access_key():
    with pytest.raises(ValidationError, match="API_ACCESS_KEY is required"):
        Settings(_env_file=None, app_env="production", api_access_key=None)
    with pytest.raises(ValidationError, match="must differ"):
        Settings(_env_file=None, api_access_key=KEY, openai_api_key=KEY)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, api_access_key="short")
    assert KEY not in repr(Settings(_env_file=None, api_access_key=KEY))


@pytest.mark.anyio
@pytest.mark.parametrize("path, method, payload", [
    ("/api/v1/analytics/sellers", "GET", None),
    ("/api/v1/analytics/query", "POST", {"domain": "sales", "metrics": ["order_count"], "sort_by": "order_count"}),
    ("/api/v1/executive/messages", "POST", {"question": "Quem vendeu mais?"}),
    ("/health/ready", "GET", None),
])
async def test_protected_routes_reject_missing_and_wrong_key(path, method, payload):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=protected_app()), base_url="http://test") as client:
        for headers in ({}, {"X-API-Key": "wrong"}):
            response = await client.request(method, path, json=payload, headers=headers)
            assert response.status_code == 401
            assert KEY not in response.text
        assert (await client.get("/health")).status_code == 200


@pytest.mark.anyio
async def test_valid_key_works_and_rate_window_resets(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(security, "monotonic", lambda: clock[0])
    monkeypatch.setattr(executive, "ask_executive", answer)
    app = protected_app(executive_requests_per_minute=1)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=HEADERS) as client:
        assert (await client.post("/api/v1/executive/messages", json={"question": "Teste"})).status_code == 200
        blocked = await client.post("/api/v1/executive/messages", json={"question": "Teste"})
        assert blocked.status_code == 429 and blocked.headers["Retry-After"] == "60"
        clock[0] = 60.0
        assert (await client.post("/api/v1/executive/messages", json={"question": "Teste"})).status_code == 200


@pytest.mark.anyio
async def test_concurrency_is_bounded_and_failure_releases_slot(monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow_failure(*args):
        entered.set()
        await release.wait()
        raise HTTPException(503, "Test failure")

    monkeypatch.setattr(executive, "ask_executive", slow_failure)
    app = protected_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=HEADERS) as client:
        first = asyncio.create_task(client.post("/api/v1/executive/messages", json={"question": "Teste"}))
        try:
            await asyncio.wait_for(entered.wait(), timeout=2)
            assert (await client.post("/api/v1/executive/messages", json={"question": "Teste"})).status_code == 429
        finally:
            release.set()
            assert (await first).status_code == 503
        monkeypatch.setattr(executive, "ask_executive", answer)
        assert (await client.post("/api/v1/executive/messages", json={"question": "Teste"})).status_code == 200


@pytest.mark.anyio
async def test_openapi_describes_header_key():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=protected_app()), base_url="http://test") as client:
        schema = (await client.get("/openapi.json")).json()
    assert schema["components"]["securitySchemes"]["APIKeyHeader"]["name"] == "X-API-Key"
    assert schema["paths"]["/api/v1/executive/messages"]["post"]["security"] == [{"APIKeyHeader": []}]
