"""Inicialização da interface HTTP do backend."""

from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from intelligent_marketplace.api.health import router as health_router
from intelligent_marketplace.core.config import Settings
from intelligent_marketplace.infrastructure.database import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    """Cria a aplicação sem abrir conexões ou criar tabelas na inicialização."""
    settings = settings if settings is not None else Settings()
    database = Database(settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            yield
        finally:
            await run_in_threadpool(database.dispose)

    application = FastAPI(
        title=settings.app_name,
        description="Backend dos agentes Logístico, Jornada do Cliente e Executivo / Orquestrador.",
        version=version("intelligent-marketplace-api"),
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.database = database
    application.include_router(health_router)
    return application


app = create_app()
