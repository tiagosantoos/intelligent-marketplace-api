"""Leitura dos CSVs sem dependência de banco ou de localização no projeto."""

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

import sqlalchemy as sa

from intelligent_marketplace.infrastructure.models.historical import metadata

# Dependency order: parents before the tables referencing them.
SOURCE_FILES = {
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "product_category_name_translation": "product_category_name_translation.csv",
    "products": "olist_products_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
}


class DatasetError(ValueError):
    """Erro de carga com mensagem segura, sem valores dos registros."""


@dataclass(frozen=True)
class FilePlan:
    table_name: str
    path: Path
    sha256: str
    row_count: int


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_value(column: sa.Column, raw: str):
    if raw == "":
        if column.nullable:
            return None
        raise ValueError("campo obrigatório vazio")
    kind = column.type
    if isinstance(kind, sa.DateTime):
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    if isinstance(kind, (sa.Integer, sa.Numeric)):
        with localcontext() as ctx:
            ctx.prec = 60
            number = Decimal(raw)
            if not number.is_finite():
                raise ValueError("número não finito")
            if isinstance(kind, sa.Integer):
                if number != number.to_integral_value() or not -(2**31) <= number < 2**31:
                    raise ValueError("inteiro inválido")
                return int(number)
            if number != number.quantize(Decimal(1).scaleb(-kind.scale)):
                raise ValueError("precisão decimal incompatível")
            if abs(number) >= Decimal(10) ** (kind.precision - kind.scale):
                raise ValueError("número excede a coluna")
            return number
    if "\x00" in raw:
        raise ValueError("caractere nulo não permitido")
    if column.primary_key and not raw.strip():
        raise ValueError("chave vazia")
    if isinstance(kind, sa.String) and kind.length and len(raw) > kind.length:
        raise ValueError("texto excede a coluna")
    return raw


def iter_rows(table_name: str, path: Path):
    table = metadata.tables[f"historical.{table_name}"]
    columns = [column for column in table.columns if column.identity is None]
    expected = {column.name for column in columns}
    try:
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source, strict=True)
            headers = reader.fieldnames or []
            if len(headers) != len(expected) or set(headers) != expected:
                raise DatasetError(f"{path.name}: cabeçalho ausente, duplicado ou incompatível")
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise DatasetError(f"{path.name}: linha {reader.line_num}: quantidade de campos inválida")
                converted = {}
                for column in columns:
                    try:
                        converted[column.name] = parse_value(column, row[column.name])
                    except (ValueError, InvalidOperation, OverflowError):
                        raise DatasetError(
                            f"{path.name}: linha {reader.line_num}: valor inválido em {column.name}"
                        ) from None
                yield converted
    except (UnicodeError, csv.Error):
        raise DatasetError(f"{path.name}: codificação UTF-8 ou estrutura CSV inválida") from None


def validate_dataset(source_dir: Path) -> list[FilePlan]:
    if not source_dir.is_dir():
        raise DatasetError("A pasta de origem não existe")
    missing = [filename for filename in SOURCE_FILES.values() if not (source_dir / filename).is_file()]
    if missing:
        raise DatasetError("Arquivos ausentes: " + ", ".join(missing))
    plans = []
    for table_name, filename in SOURCE_FILES.items():
        path = source_dir / filename
        initial_hash = file_hash(path)
        table = metadata.tables[f"historical.{table_name}"]
        keys = [column.name for column in table.primary_key if column.identity is None]
        seen = set()
        count = 0
        for row in iter_rows(table_name, path):
            if keys:
                key = tuple(row[name] for name in keys)
                if key in seen:
                    raise DatasetError(f"{filename}: chave primária repetida no registro {count + 1}")
                seen.add(key)
            count += 1
        if count == 0:
            raise DatasetError(f"{filename}: arquivo sem registros")
        if file_hash(path) != initial_hash:
            raise DatasetError(f"{filename}: arquivo mudou durante a validação")
        plans.append(FilePlan(table_name, path, initial_hash, count))
    return plans
