import csv
import os
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from intelligent_marketplace.core.config import Settings
from intelligent_marketplace.importing.cli import main
from intelligent_marketplace.importing.dataset import (
    SOURCE_FILES, DatasetError, iter_rows, validate_dataset,
)
from intelligent_marketplace.importing.service import import_dataset
from intelligent_marketplace.infrastructure.database import Database
from intelligent_marketplace.infrastructure.models.historical import metadata


def write_rows(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def change_value(path, column, value):
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    rows[0][column] = value
    write_rows(path, rows)


@pytest.fixture
def dataset_dir(tmp_path):
    order = {
        "order_id": "a" * 32, "customer_id": "b" * 32, "order_status": "delivered",
        "order_purchase_timestamp": "2018-01-01 10:00:00", "order_approved_at": "",
        "order_delivered_carrier_date": "2018-01-02 10:00:00",
        "order_delivered_customer_date": "2018-01-03 10:00:00",
        "order_estimated_delivery_date": "2018-01-05 00:00:00",
    }
    review = {
        "review_id": "f" * 32, "order_id": "a" * 32, "review_score": "1",
        "review_comment_title": "", "review_comment_message": 'Texto com vírgula, "aspas"\ne outra linha',
        "review_creation_date": "2018-01-03 00:00:00",
        "review_answer_timestamp": "2018-01-04 10:00:00",
    }
    geo = {
        "geolocation_zip_code_prefix": "01001", "geolocation_lat": "-23.12345678901234567890",
        "geolocation_lng": "-46.12345678901234567890",
        "geolocation_city": "cidade", "geolocation_state": "SP",
    }
    rows = {
        "customers": [{"customer_id": "b" * 32, "customer_unique_id": "c" * 32, "customer_zip_code_prefix": "01001", "customer_city": "cidade", "customer_state": "SP"}],
        "sellers": [{"seller_id": "d" * 32, "seller_zip_code_prefix": "01001", "seller_city": "cidade", "seller_state": "SP"}],
        "product_category_name_translation": [{"product_category_name": "categoria", "product_category_name_english": "category"}],
        "products": [{"product_id": "e" * 32, "product_category_name": "categoria", "product_name_lenght": "10.0", "product_description_lenght": "", "product_photos_qty": "1", "product_weight_g": "", "product_length_cm": "1.0", "product_height_cm": "1.0", "product_width_cm": "1.0"}],
        "orders": [order, {**order, "order_id": "1" * 32}],
        "order_items": [{"order_id": "a" * 32, "order_item_id": "1", "product_id": "e" * 32, "seller_id": "d" * 32, "shipping_limit_date": "2018-01-02 00:00:00", "price": "123.45", "freight_value": "0.00"}],
        "order_payments": [{"order_id": "a" * 32, "payment_sequential": "1", "payment_type": "credit_card", "payment_installments": "1", "payment_value": "123.45"}],
        "order_reviews": [review, {**review, "order_id": "1" * 32}],
        "geolocation": [geo, geo.copy()],
    }
    for table, records in rows.items():
        write_rows(tmp_path / SOURCE_FILES[table], records)
    return tmp_path


def test_complete_validation_preserves_source_occurrences(dataset_dir):
    plans = validate_dataset(dataset_dir)
    counts = {p.table_name: p.row_count for p in plans}
    assert len(plans) == 9
    assert counts["geolocation"] == counts["order_reviews"] == 2
    assert all(len(p.sha256) == 64 for p in plans)


def test_types_bom_optional_fields_and_multiline_comments(dataset_dir):
    product = next(iter_rows("products", dataset_dir / SOURCE_FILES["products"]))
    item = next(iter_rows("order_items", dataset_dir / SOURCE_FILES["order_items"]))
    geo = next(iter_rows("geolocation", dataset_dir / SOURCE_FILES["geolocation"]))
    review = next(iter_rows("order_reviews", dataset_dir / SOURCE_FILES["order_reviews"]))
    assert product["product_name_lenght"] == 10
    assert product["product_weight_g"] is None
    assert item["price"] == Decimal("123.45")
    assert geo["geolocation_zip_code_prefix"] == "01001"
    assert geo["geolocation_lat"] == Decimal("-23.12345678901234567890")
    assert "\n" in review["review_comment_message"]


@pytest.mark.parametrize(
    ("table", "column", "value"),
    [
        ("products", "product_name_lenght", "1.5"),
        ("order_items", "price", "NaN"),
        ("order_items", "price", "1.234"),
        ("orders", "order_purchase_timestamp", "invalid"),
        ("orders", "order_status", ""),
        ("sellers", "seller_state", "TOO-LONG"),
    ],
)
def test_invalid_values_fail_without_echoing_input(dataset_dir, table, column, value):
    change_value(dataset_dir / SOURCE_FILES[table], column, value)
    with pytest.raises(DatasetError, match=column):
        validate_dataset(dataset_dir)


def test_missing_file_and_incompatible_header(dataset_dir):
    path = dataset_dir / SOURCE_FILES["orders"]
    path.write_text("wrong_header\nvalue\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="cabeçalho"):
        validate_dataset(dataset_dir)
    path.unlink()
    with pytest.raises(DatasetError, match="Arquivos ausentes"):
        validate_dataset(dataset_dir)


def test_duplicate_source_primary_key_is_rejected(dataset_dir):
    path = dataset_dir / SOURCE_FILES["orders"]
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    write_rows(path, [rows[0], rows[0]])
    with pytest.raises(DatasetError, match="chave primária repetida"):
        validate_dataset(dataset_dir)


def test_validation_only_does_not_require_valid_database_settings(dataset_dir, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "invalid")
    assert main(["--source-dir", str(dataset_dir), "--validate-only"]) == 0
    assert '"mode": "validation"' in capsys.readouterr().out


def test_cli_reports_validation_failure_without_writing(dataset_dir, capsys):
    change_value(dataset_dir / SOURCE_FILES["orders"], "customer_id", "")
    assert main(["--source-dir", str(dataset_dir), "--validate-only"]) == 2
    assert "customer_id" in capsys.readouterr().err


@pytest.fixture
def postgres_import_connection():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Defina TEST_DATABASE_URL para um banco exclusivo de testes")
    database = Database(Settings(_env_file=None, database_url=url))
    try:
        with database.engine.connect() as connection:
            transaction = connection.begin()
            try:
                if connection.scalar(text("SELECT to_regnamespace('historical')")) is not None:
                    pytest.skip("Utilize um banco vazio de testes")
                if inspect(connection).has_table("alembic_version", schema="public"):
                    pytest.skip("Utilize um banco sem migrações anteriores")
                config = Config("alembic.ini")
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
                yield connection
            finally:
                transaction.rollback()
    finally:
        database.dispose()


@pytest.mark.integration
def test_import_reexecution_and_changed_file_protection(dataset_dir, postgres_import_connection):
    connection = postgres_import_connection
    plans = validate_dataset(dataset_dir)
    first = import_dataset(connection, plans, batch_size=1)
    assert all(r["status"] == "imported" for r in first)
    repeated = import_dataset(connection, plans, batch_size=2)
    assert all(r["status"] == "skipped" for r in repeated)
    for plan in plans:
        table = metadata.tables[f"historical.{plan.table_name}"]
        assert connection.scalar(select(func.count()).select_from(table)) == plan.row_count
    change_value(dataset_dir / SOURCE_FILES["geolocation"], "geolocation_city", "outra cidade")
    changed_plans = validate_dataset(dataset_dir)
    with pytest.raises(DatasetError, match="conteúdo diferente"):
        with connection.begin_nested():
            import_dataset(connection, changed_plans)
    assert connection.scalar(select(func.count()).select_from(metadata.tables["historical.geolocation"])) == 2


@pytest.mark.integration
def test_foreign_key_failure_rolls_back_all_imported_tables(dataset_dir, postgres_import_connection):
    connection = postgres_import_connection
    change_value(dataset_dir / SOURCE_FILES["orders"], "customer_id", "9" * 32)
    plans = validate_dataset(dataset_dir)
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            import_dataset(connection, plans)
    for table in metadata.tables.values():
        assert connection.scalar(select(func.count()).select_from(table)) == 0
