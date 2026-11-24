"""Seleciona uma role de leitura após neon deploy/env pull, sem exibir sua URL."""

import argparse
import shutil
import subprocess

from dotenv import set_key
from sqlalchemy import text
from sqlalchemy.engine import make_url

from intelligent_marketplace.core.config import Settings
from intelligent_marketplace.infrastructure.database import Database


def main():
    parser = argparse.ArgumentParser(description="Configurar a URL pooled de runtime e preservar a URL administrativa direta")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--role", default="marketplace_runtime")
    parser.add_argument("--file", default=".env")
    args = parser.parse_args()
    database = None
    try:
        cli = shutil.which("neon")
        if cli is None:
            raise ValueError("Instale o CLI neon antes de selecionar a role")
        result = subprocess.run([cli, "connection-string", args.branch, "--role-name", args.role, "--pooled"], capture_output=True, text=True, check=True, timeout=60)
        url = result.stdout.strip()
        parsed = make_url(url)
        if parsed.username != args.role or parsed.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
            raise ValueError("Role ou TLS não corresponde à configuração esperada")
        settings = Settings(_env_file=None, app_env="test", database_url=url, database_url_unpooled=None, api_access_key=None, openai_api_key=None)
        database = Database(settings)
        with database.engine.connect() as connection:
            permissions = connection.execute(text("SELECT has_table_privilege(current_user,'historical.orders','SELECT') AS can_read, has_table_privilege(current_user,'historical.orders','INSERT') OR has_table_privilege(current_user,'historical.orders','UPDATE') OR has_table_privilege(current_user,'historical.orders','DELETE') AS can_write")).mappings().one()
            if not permissions["can_read"] or permissions["can_write"]:
                raise ValueError("A role deve permitir leitura e recusar escrita em historical.orders")
        set_key(args.file, "DATABASE_URL", url, quote_mode="always")
        print("Runtime PostgreSQL: leitura confirmada; URL pooled salva sem exibição; demais variáveis preservadas.")
        return 0
    except Exception as error:
        print(f"Não foi possível configurar runtime ({type(error).__name__}); nenhuma credencial foi exibida.")
        return 1
    finally:
        if database is not None:
            database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
