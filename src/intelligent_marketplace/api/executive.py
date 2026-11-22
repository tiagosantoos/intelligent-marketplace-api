"""Interface inicial do Executivo; requisições independentes, sem memória persistente."""

from fastapi import APIRouter, Request

from intelligent_marketplace.agents.executive.assistant import ExecutiveAnswer, ExecutiveQuestion, ask_executive

router = APIRouter(prefix="/api/v1/executive", tags=["Executive"])


@router.post("/messages", response_model=ExecutiveAnswer)
async def messages(payload: ExecutiveQuestion, request: Request):
    return await ask_executive(payload.question, request.app.state.database, request.app.state.settings)
