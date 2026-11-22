import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from agents import Model, ModelResponse
from agents.exceptions import MaxTurnsExceeded
from agents.usage import Usage
from openai import OpenAIError
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

from test_importing import postgres_import_connection
from test_analytics import analytics_session
from intelligent_marketplace.agents.executive import assistant
from intelligent_marketplace.core.config import Settings
from intelligent_marketplace.main import create_app
from intelligent_marketplace.services.analysis_plan import AnalysisPlan


@pytest.fixture
def ai_settings():
    return Settings(_env_file=None, database_url=None, openai_api_key="test-key-never-sent", openai_model="test-model")


@pytest.mark.anyio
async def test_missing_configuration_does_not_call_openai(app_settings, monkeypatch):
    monkeypatch.setattr(assistant.Runner, "run", AsyncMock(side_effect=AssertionError("Unexpected call")))
    app_settings.openai_api_key = None
    app_settings.openai_model = None
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(app_settings)), base_url="http://test") as client:
        response = await client.post("/api/v1/executive/messages", json={"question": "Qual vendedor mais vendeu?"})
    assert response.status_code == 503
    assert response.json() == {"detail": "OpenAI is not configured"}


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [{"question": " "}, {"question": "x" * 4001}, {"question": "x", "sql": "SELECT 1"}])
async def test_input_validation(app_settings, payload):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(app_settings)), base_url="http://test") as client:
        response = await client.post("/api/v1/executive/messages", json=payload)
    assert response.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize("error, status", [(OpenAIError("secret-driver-details"), 502), (TimeoutError("secret-timeout"), 504), (MaxTurnsExceeded("secret-turn-limit"), 502)])
async def test_provider_failures_are_sanitized(ai_settings, monkeypatch, error, status):
    app = create_app(ai_settings)
    app.state.database.session_factory = object()
    monkeypatch.setattr(assistant.Runner, "run", AsyncMock(side_effect=error))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/executive/messages", json={"question": "Analise os atrasos"})
    assert response.status_code == status
    assert "secret" not in response.text


@pytest.mark.anyio
async def test_database_required_before_provider_call(ai_settings, monkeypatch):
    runner = AsyncMock()
    monkeypatch.setattr(assistant.Runner, "run", runner)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(ai_settings)), base_url="http://test") as client:
        response = await client.post("/api/v1/executive/messages", json={"question": "Qual estado atrasou mais?"})
    assert response.status_code == 503
    runner.assert_not_called()


def test_openai_secrets_and_empty_settings():
    settings = Settings(_env_file=None, openai_api_key="private-test-key", openai_model="  test-model  ")
    assert "private-test-key" not in repr(settings)
    assert settings.openai_model == "test-model"
    empty = Settings(_env_file=None, openai_api_key="  ", openai_model=" ")
    assert empty.openai_api_key is empty.openai_model is None


class ScriptedModel(Model):
    """Modelo local que exercita o Runner real, sem acesso a um provedor externo."""

    def __init__(self):
        self.calls = 0

    async def get_response(self, system_instructions, input, model_settings, tools, output_schema, handoffs, tracing, **kwargs):
        self.calls += 1
        assert tracing.is_disabled()
        assert model_settings.store is False
        if self.calls <= 2:
            name, filters = (
                ("sales_by_seller", {"sort_by": "order_count", "limit": 1, "start_date": None, "end_date": None})
                if self.calls == 1 else
                ("delays_by_state", {"sort_by": "late_order_count", "limit": 1, "min_delivered_orders": 1, "start_date": None, "end_date": None})
            )
            output = [ResponseFunctionToolCall(id=f"fc{self.calls}", call_id=f"call{self.calls}", name=name, arguments=json.dumps({"filters": filters}), type="function_call")]
        else:
            results = [json.loads(item["output"]) for item in input if item.get("type") == "function_call_output"]
            assert results[0]["data"][0]["order_count"] == 4
            assert results[1]["data"][0]["late_order_count"] == 2
            final = {"answer": "O vendedor A teve 4 pedidos. RJ teve 2 entregas atrasadas entre 3 elegíveis.", "evidence_ids": [1, 2]}
            output = [ResponseOutputMessage(id="message1", role="assistant", status="completed", type="message", content=[ResponseOutputText(type="output_text", text=json.dumps(final), annotations=[])])]
        return ModelResponse(output=output, usage=Usage(), response_id=f"response{self.calls}")

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError
        yield


@pytest.mark.integration
@pytest.mark.anyio
async def test_real_runner_tools_database_and_http_response(analytics_session, ai_settings, monkeypatch):
    @contextmanager
    def transactional_session(database, settings):
        # A fixture de banco mantém a carga sintética em uma transação descartável.
        yield analytics_session

    model = ScriptedModel()
    monkeypatch.setattr(assistant, "analytics_session", transactional_session)
    monkeypatch.setattr(assistant, "OpenAIProvider", lambda **kwargs: SimpleNamespace(get_model=lambda name: model))
    app = create_app(ai_settings)
    app.state.database.session_factory = object()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/executive/messages", json={"question": "Quem vendeu mais e qual estado concentrou atrasos?"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert model.calls == 3
    assert body["model"] == "test-model"
    assert body["evidence"][0]["data"][0]["seller_id"] == "A"
    assert body["evidence"][1]["data"][0]["late_rate_percent"] == "66.67"
    assert "4 pedidos" in body["answer"]


class SellerDelayModel(ScriptedModel):
    async def get_response(self, system_instructions, input, model_settings, tools, output_schema, handoffs, tracing, **kwargs):
        if self.calls == 0:
            return await super().get_response(system_instructions, input, model_settings, tools, output_schema, handoffs, tracing, **kwargs)
        self.calls += 1
        if self.calls == 2:
            plan = AnalysisPlan(domain="delivery", group_by=["seller_id"], metrics=["late_order_count", "late_rate_percent", "max_late_days", "avg_late_days"], sort_by="late_order_count", limit=1)
            output = [ResponseFunctionToolCall(id="flex1", call_id="flex1", name="marketplace_analysis", arguments=json.dumps({"plan": plan.model_dump(mode="json")}), type="function_call")]
        else:
            reports = [json.loads(item["output"]) for item in input if item.get("type") == "function_call_output"]
            assert reports[-1]["data"][0]["late_order_count"] == 2
            final = {"answer": "O vendedor A está associado a 2 pedidos atrasados entre 3 elegíveis (66,67%). Isso não comprova responsabilidade pelo atraso.", "evidence_ids": [reports[-1]["evidence_id"]]}
            output = [ResponseOutputMessage(id="final", role="assistant", status="completed", type="message", content=[ResponseOutputText(type="output_text", text=json.dumps(final), annotations=[])])]
        return ModelResponse(output=output, usage=Usage(), response_id=f"flex-response-{self.calls}")


class RecoveringPlanModel(SellerDelayModel):
    async def get_response(self, system_instructions, input, model_settings, tools, output_schema, handoffs, tracing, **kwargs):
        if self.calls == 0:
            self.calls = 1
            plan = AnalysisPlan(domain="sales", metrics=["item_revenue"], sort_by="item_revenue").model_dump(mode="json")
            plan["domain"] = "delivery"  # Deve ser recusado sem executar SQL e permitir correção.
            output = [ResponseFunctionToolCall(id="invalid", call_id="invalid", name="marketplace_analysis", arguments=json.dumps({"plan": plan}), type="function_call")]
            return ModelResponse(output=output, usage=Usage(), response_id="invalid-response")
        if self.calls == 1:
            outputs = [json.loads(item["output"]) for item in input if item.get("type") == "function_call_output"]
            assert outputs[-1]["error"] == "invalid_analysis_plan"
        return await super().get_response(system_instructions, input, model_settings, tools, output_schema, handoffs, tracing, **kwargs)


@pytest.mark.integration
@pytest.mark.anyio
@pytest.mark.parametrize("model_type", [SellerDelayModel, RecoveringPlanModel])
async def test_flexible_tool_answers_seller_delay_and_excludes_irrelevant_evidence(analytics_session, ai_settings, monkeypatch, model_type):
    @contextmanager
    def transactional_session(database, settings):
        yield analytics_session

    model = model_type()
    monkeypatch.setattr(assistant, "analytics_session", transactional_session)
    monkeypatch.setattr(assistant, "OpenAIProvider", lambda **kwargs: SimpleNamespace(get_model=lambda name: model))
    app = create_app(ai_settings)
    app.state.database.session_factory = object()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/executive/messages", json={"question": "Qual vendedor tem mais pedidos atrasados?"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["evidence"]) == 1
    assert body["evidence"][0]["plan"]["domain"] == "delivery"
    assert body["evidence"][0]["data"][0]["late_order_count"] == 2
    assert "66,67%" in body["answer"]


@pytest.mark.anyio
async def test_invented_evidence_reference_is_rejected(ai_settings, monkeypatch):
    app = create_app(ai_settings)
    app.state.database.session_factory = object()
    monkeypatch.setattr(assistant.Runner, "run", AsyncMock(return_value=SimpleNamespace(final_output=assistant.ExecutiveDecision(answer="Answer", evidence_ids=[1]))))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/executive/messages", json={"question": "Analise atrasos"})
    assert response.status_code == 502
