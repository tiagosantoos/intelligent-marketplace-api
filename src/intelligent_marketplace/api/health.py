"""Verificação de disponibilidade do processo HTTP."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("/health", response_model=HealthResponse, summary="Verificar a disponibilidade da API")
async def health() -> HealthResponse:
    """Confirma que a API responde; não verifica banco ou integrações externas."""
    return HealthResponse(status="ok")
