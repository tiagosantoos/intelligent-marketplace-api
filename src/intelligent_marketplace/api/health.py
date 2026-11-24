"""Verificação de disponibilidade do processo HTTP."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from intelligent_marketplace.api.security import require_api_key

from intelligent_marketplace.infrastructure.database import (
    Database,
    DatabaseNotConfiguredError,
    get_database,
)

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ready"]
    database: Literal["connected"]


@router.get("/health", response_model=HealthResponse, summary="Verificar a disponibilidade da API")
async def health() -> HealthResponse:
    """Confirma que a API responde; não verifica banco ou integrações externas."""
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Verificar a conexão com o banco",
    responses={503: {"description": "Banco não configurado ou indisponível"}},
    dependencies=[Depends(require_api_key)],
)
def readiness(database: Annotated[Database, Depends(get_database)]) -> ReadinessResponse:
    """Verifica somente a conexão, sem validar schemas ou tabelas nesta etapa.

    A rota síncrona executa no threadpool do FastAPI para não bloquear o event loop.
    """
    try:
        database.check_connection()
    except DatabaseNotConfiguredError:
        raise HTTPException(status_code=503, detail="Database is not configured") from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database is unavailable") from None
    return ReadinessResponse(status="ready", database="connected")
