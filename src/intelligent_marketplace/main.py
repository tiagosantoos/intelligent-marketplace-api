"""Inicialização da interface HTTP do backend."""

from importlib.metadata import version

from fastapi import FastAPI

from intelligent_marketplace.api.health import router as health_router


def create_app() -> FastAPI:
    """Cria a aplicação sem depender de banco ou serviços externos."""
    application = FastAPI(
        title="Intelligent Marketplace API",
        description="Backend dos agentes Logístico, Jornada do Cliente e Executivo / Orquestrador.",
        version=version("intelligent-marketplace-api"),
    )
    application.include_router(health_router)
    return application


app = create_app()
