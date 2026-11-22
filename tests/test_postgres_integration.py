"""Integração opcional: apenas SELECT 1; não cria ou remove dados."""

import os

import pytest

from intelligent_marketplace.core.config import Settings
from intelligent_marketplace.infrastructure.database import Database


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
