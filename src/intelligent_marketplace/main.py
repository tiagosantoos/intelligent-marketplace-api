"""Inicialização da interface HTTP do backend."""

from importlib.metadata import version

from fastapi import FastAPI

from intelligent_marketplace.api.health import router as health_router
from intelligent_marketplace.core.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Cria a aplicação sem depender de banco ou serviços externos."""
    settings = settings if settings is not None else Settings()
    application = FastAPI(
        title=settings.app_name,
        description="Backend dos agentes Logístico, Jornada do Cliente e Executivo / Orquestrador.",
        version=version("intelligent-marketplace-api"),
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    application.state.settings = settings
    application.include_router(health_router)
    return application


app = create_app()
