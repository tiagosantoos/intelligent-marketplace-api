"""Conexões e sessões PostgreSQL, sem criação automática de tabelas."""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException, Request
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from intelligent_marketplace.core.config import Settings


class DatabaseNotConfiguredError(RuntimeError):
    """Não há conexão configurada para esta aplicação."""


class Database:
    def __init__(self, settings: Settings, *, use_unpooled: bool = False):
        self.engine: Engine | None = None
        self.session_factory: sessionmaker[Session] | None = None
        database_url = (
            settings.database_url_unpooled
            if use_unpooled and settings.database_url_unpooled is not None
            else settings.database_url
        )
        if database_url is not None:
            timeout = settings.database_connect_timeout_seconds
            self.engine = create_engine(
                database_url.get_secret_value(),
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
                pool_timeout=timeout,
                connect_args={"connect_timeout": timeout},
                hide_parameters=True,
            )
            self.session_factory = sessionmaker(
                bind=self.engine, autoflush=False, expire_on_commit=False
            )

    def check_connection(self) -> None:
        """Executa uma consulta sem modificar dados. O engine conecta sob demanda."""
        if self.engine is None:
            raise DatabaseNotConfiguredError
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def dispose(self) -> None:
        if self.engine is not None:
            self.engine.dispose()


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_session(request: Request) -> Iterator[Session]:
    """Sessão por requisição. O serviço decide quando confirmar uma transação."""
    database = get_database(request)
    if database.session_factory is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    with database.session_factory() as session:
        yield session


def get_analytics_session(request: Request) -> Iterator[Session]:
    """Transação de leitura com timeout, também obrigatório para ferramentas futuras."""
    with analytics_session(get_database(request), request.app.state.settings) as session:
        yield session


@contextmanager
def analytics_session(database: Database, settings: Settings) -> Iterator[Session]:
    """Compartilha as mesmas proteções entre as rotas HTTP e as ferramentas de IA."""
    if database.session_factory is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    try:
        with database.session_factory() as session:
            with session.begin():
                session.execute(text("SET TRANSACTION READ ONLY"))
                session.execute(
                    text("SELECT set_config('statement_timeout', :timeout, true)"),
                    {"timeout": f"{settings.analytics_query_timeout_seconds}s"},
                )
                yield session
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Analytics are temporarily unavailable") from None
