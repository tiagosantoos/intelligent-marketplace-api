"""Carga atômica: o chamador deve fornecer uma conexão dentro de transação."""

from itertools import islice

from sqlalchemy import Connection, func, select, text

from intelligent_marketplace.importing.dataset import DatasetError, FilePlan, file_hash, iter_rows
from intelligent_marketplace.infrastructure.models.historical import dataset_imports, metadata


def import_dataset(connection: Connection, plans: list[FilePlan], batch_size: int = 2000) -> list[dict]:
    if not connection.in_transaction():
        raise DatasetError("A importação exige uma transação aberta")
    if not 1 <= batch_size <= 10000:
        raise DatasetError("O tamanho do lote deve estar entre 1 e 10000")
    # Prevent concurrent invocations from racing on data and the load registry.
    connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 0x494D504F5254})
    report = []
    for plan in plans:
        table = metadata.tables[f"historical.{plan.table_name}"]
        if file_hash(plan.path) != plan.sha256:
            raise DatasetError(f"{plan.path.name}: arquivo mudou após a validação")
        previous = connection.execute(
            select(dataset_imports).where(dataset_imports.c.table_name == plan.table_name)
        ).mappings().one_or_none()
        if previous is not None:
            if previous["file_sha256"] != plan.sha256 or previous["row_count"] != plan.row_count:
                raise DatasetError(f"{plan.path.name}: conteúdo diferente de uma carga anterior; substituição automática bloqueada")
            actual_count = connection.scalar(select(func.count()).select_from(table))
            if actual_count != previous["row_count"]:
                raise DatasetError(f"{plan.table_name}: contagem diverge da carga registrada; verifique o banco")
            report.append({"table": plan.table_name, "rows": plan.row_count, "status": "skipped"})
            continue
        if connection.execute(select(table.c[next(iter(table.c.keys()))]).limit(1)).first() is not None:
            raise DatasetError(f"{plan.table_name}: tabela possui dados sem registro de importação")
        rows = iter(iter_rows(plan.table_name, plan.path))
        imported = 0
        while batch := list(islice(rows, batch_size)):
            connection.execute(table.insert(), batch)
            imported += len(batch)
        if imported != plan.row_count or file_hash(plan.path) != plan.sha256:
            raise DatasetError(f"{plan.path.name}: arquivo mudou durante a carga")
        connection.execute(dataset_imports.insert().values(
            table_name=plan.table_name, file_sha256=plan.sha256, row_count=imported
        ))
        report.append({"table": plan.table_name, "rows": imported, "status": "imported"})
    return report
