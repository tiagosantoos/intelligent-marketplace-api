"""Comando independente da API para conferir e carregar o histórico."""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from intelligent_marketplace.core.config import Settings
from intelligent_marketplace.importing.dataset import DatasetError, validate_dataset
from intelligent_marketplace.importing.service import import_dataset
from intelligent_marketplace.infrastructure.database import Database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validar ou importar os nove CSVs históricos")
    parser.add_argument("--source-dir", type=Path, required=True, help="Pasta com os CSVs originais")
    parser.add_argument("--validate-only", action="store_true", help="Validar sem acessar o banco")
    parser.add_argument("--batch-size", type=int, default=2000, help="Linhas por lote, de 1 a 10000")
    args = parser.parse_args(argv)
    if not 1 <= args.batch_size <= 10000:
        parser.error("--batch-size deve estar entre 1 e 10000")
    database = None
    try:
        plans = validate_dataset(args.source_dir)
        if args.validate_only:
            report = [{"table": p.table_name, "rows": p.row_count, "status": "validated"} for p in plans]
            mode = "validation"
        else:
            database = Database(Settings(), use_unpooled=True)
            if database.engine is None:
                raise DatasetError("Configure DATABASE_URL para importar; --validate-only não exige banco")
            with database.engine.begin() as connection:
                report = import_dataset(connection, plans, args.batch_size)
            mode = "import"
        print(json.dumps({"mode": mode, "tables": report, "total_rows": sum(p.row_count for p in plans)}, ensure_ascii=False, indent=2))
        return 0
    except DatasetError as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except SQLAlchemyError:
        print(json.dumps({"error": "Falha no banco; a carga foi revertida. Confira conexão, migrações e referências entre os arquivos."}, ensure_ascii=False), file=sys.stderr)
        return 1
    except (OSError, ValueError):
        # Configuration validation may contain secrets in structured exception data.
        print(json.dumps({"error": "Não foi possível ler os arquivos ou validar a configuração."}, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        if database is not None:
            database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
