"""Ambiente Alembic: usa a configuração do backend, sem credenciais no .ini."""

from alembic import context

from intelligent_marketplace.core.config import Settings
from intelligent_marketplace.infrastructure.database import Database
from intelligent_marketplace.infrastructure.models import metadata


def include_name(name, type_, parent_names):
    # Restrict autogeneration to the schema owned by the current models.
    return name == "historical" if type_ == "schema" else True


def run_with_connection(connection):
    context.configure(
        connection=connection,
        target_metadata=metadata,
        include_schemas=True,
        include_name=include_name,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    # SQL generation never requires credentials or a live database.
    context.configure(
        dialect_name="postgresql", target_metadata=metadata,
        literal_binds=True, include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    external_connection = context.config.attributes.get("connection")
    if external_connection is not None:
        run_with_connection(external_connection)
    else:
        database = Database(Settings())
        if database.engine is None:
            raise RuntimeError("Configure DATABASE_URL antes de executar as migrações")
        try:
            with database.engine.connect() as connection:
                run_with_connection(connection)
        finally:
            database.dispose()
