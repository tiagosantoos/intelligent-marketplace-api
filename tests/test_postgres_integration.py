"""Integração opcional: conexão e migração em banco exclusivo de testes."""

import os

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from intelligent_marketplace.core.config import Settings
from intelligent_marketplace.infrastructure.database import Database
from intelligent_marketplace.infrastructure.models import metadata


@pytest.mark.integration
def test_postgres_connection():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Defina TEST_DATABASE_URL para verificar um PostgreSQL real")
    database = Database(Settings(_env_file=None, database_url=url))
    try:
        database.check_connection()
    finally:
        database.dispose()


@pytest.mark.integration
def test_migration_roundtrip_matches_models():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Defina TEST_DATABASE_URL para um banco exclusivo de testes")
    database = Database(Settings(_env_file=None, database_url=url))
    try:
        with database.engine.connect() as connection:
            transaction = connection.begin()
            try:
                if connection.scalar(text("SELECT to_regnamespace('historical')")) is not None:
                    pytest.skip("O schema historical já existe; utilize um banco vazio de testes")
                if inspect(connection).has_table("alembic_version", schema="public"):
                    pytest.skip("Banco já possui migrações; utilize um banco vazio de testes")
                config = Config("alembic.ini")
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
                assert set(inspect(connection).get_table_names(schema="historical")) == {
                    table.name for table in metadata.tables.values()
                }
                migration_context = MigrationContext.configure(
                    connection,
                    opts={
                        "include_schemas": True,
                        "include_name": lambda name, type_, parents: (
                            name == "historical" if type_ == "schema" else True
                        ),
                        "compare_type": True,
                    },
                )
                assert compare_metadata(migration_context, metadata) == []
                command.downgrade(config, "base")
                assert connection.scalar(text("SELECT to_regnamespace('historical')")) is None
            finally:
                transaction.rollback()
    finally:
        database.dispose()
