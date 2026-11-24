from unittest.mock import patch

import pytest
from sqlalchemy.engine import make_url

from intelligent_marketplace.core.config import Settings
from intelligent_marketplace.infrastructure.database import Database


@pytest.mark.parametrize("prefix", ["postgresql", "postgres", "postgresql+psycopg"])
def test_neon_urls_preserve_credentials_and_tls_parameters(prefix):
    settings = Settings(_env_file=None, database_url=f"{prefix}://user:p%40ssword@db-pooler.example/neondb?sslmode=require&channel_binding=require", database_url_unpooled=f"{prefix}://user:p%40ssword@db.example/neondb?sslmode=require")
    pooled = make_url(settings.database_url.get_secret_value())
    direct = make_url(settings.database_url_unpooled.get_secret_value())
    assert pooled.drivername == direct.drivername == "postgresql+psycopg"
    assert pooled.password == direct.password == "p@ssword"
    assert pooled.query == {"sslmode": "require", "channel_binding": "require"}
    assert "p@ssword" not in repr(settings)


def test_runtime_uses_pooled_url_and_administration_prefers_direct():
    settings = Settings(_env_file=None, database_url="postgresql://user:pass@pooled.example/db", database_url_unpooled="postgresql://user:pass@direct.example/db")
    with patch("intelligent_marketplace.infrastructure.database.create_engine") as engine:
        Database(settings)
        assert make_url(engine.call_args.args[0]).host == "pooled.example"
        Database(settings, use_unpooled=True)
        assert make_url(engine.call_args.args[0]).host == "direct.example"


def test_direct_connection_is_optional_and_supports_unpooled_only_administration():
    settings = Settings(_env_file=None, database_url="postgresql://user:pass@db.example/db", database_url_unpooled=None)
    with patch("intelligent_marketplace.infrastructure.database.create_engine") as engine:
        Database(settings, use_unpooled=True)
        assert make_url(engine.call_args.args[0]).host == "db.example"
    direct_only = Settings(_env_file=None, database_url=None, database_url_unpooled="postgresql://user:pass@direct.example/db")
    assert Database(direct_only).engine is None
    with patch("intelligent_marketplace.infrastructure.database.create_engine") as engine:
        Database(direct_only, use_unpooled=True)
        assert make_url(engine.call_args.args[0]).host == "direct.example"
