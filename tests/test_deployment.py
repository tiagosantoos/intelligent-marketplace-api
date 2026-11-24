from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from test_importing import postgres_import_connection


@pytest.mark.integration
def test_runtime_role_can_read_historical_but_not_change_it(postgres_import_connection):
    connection = postgres_import_connection
    connection.exec_driver_sql(Path("scripts/neon-runtime-role.sql").read_text(encoding="utf-8"))
    assert connection.scalar(text("SELECT has_table_privilege('marketplace_runtime', 'historical.orders', 'SELECT')"))
    assert not connection.scalar(text("SELECT has_table_privilege('marketplace_runtime', 'historical.orders', 'INSERT')"))
    assert not connection.scalar(text("SELECT has_table_privilege('marketplace_runtime', 'historical.orders', 'UPDATE')"))
    assert not connection.scalar(text("SELECT has_table_privilege('marketplace_runtime', 'historical.orders', 'DELETE')"))
    connection.execute(text("SET LOCAL ROLE marketplace_runtime"))
    assert connection.scalar(text("SELECT count(*) FROM historical.orders")) == 0
    with pytest.raises(ProgrammingError):
        with connection.begin_nested():
            connection.execute(text("DELETE FROM historical.orders"))
