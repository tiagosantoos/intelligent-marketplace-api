"""Carga pequena e reproduzível, independente dos CSVs e das fixtures de pytest."""

import hashlib
import json
from datetime import datetime

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import make_url

from intelligent_marketplace.infrastructure.models.historical import (
    customers, sellers, products, orders, order_items, order_reviews, metadata,
)

DATASET_VERSION = "executive-synthetic-v1"


def validate_evaluation_url(url):
    try:
        parsed = make_url(url)
        valid = (
            parsed.drivername == "postgresql+psycopg"
            and parsed.host in {"127.0.0.1", "localhost", "::1"}
            and parsed.database is not None and parsed.database.endswith("_eval")
        )
    except Exception:
        valid = False
    if not valid:
        raise ValueError("Use um PostgreSQL local exclusivo com nome terminado em _eval")


def prepare_database(connection):
    if connection.scalar(text("SELECT to_regnamespace('historical')")) is not None or inspect(connection).get_table_names(schema="public"):
        raise ValueError("A avaliação exige um banco vazio; nenhum dado existente será substituído")
    config = Config("alembic.ini")
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
    seed_dataset(connection)


def seed_dataset(connection):
    """Insere a fixture uma vez; não apaga nem substitui registros existentes."""
    connection.execute(customers.insert(), [dict(customer_id=s, customer_unique_id=s, customer_zip_code_prefix="01001", customer_city="synthetic", customer_state=s) for s in ("SP", "RJ", "AL")])
    connection.execute(sellers.insert(), [dict(seller_id=s, seller_zip_code_prefix="01001", seller_city="synthetic", seller_state="SP") for s in ("A", "B")])
    connection.execute(products.insert(), {"product_id": "P", "product_category_name": "synthetic_category"})
    cases = [
        ("1", "SP", "delivered", "2020-01-31 23:59:59", "2020-02-03 20:00:00", [("A", 10), ("A", 20), ("B", 30)]),
        ("2", "RJ", "delivered", "2020-01-01", "2020-02-04", [("A", 40)]),
        ("3", "RJ", "delivered", "2020-02-01", "2020-02-02", [("B", 50)]),
        ("4", "AL", "canceled", "2020-01-01", "2020-02-04", [("B", 1000)]),
        ("5", "AL", "delivered", "2020-01-01", None, [("A", 60)]),
        ("6", "AL", "delivered", "2020-01-01", "2020-02-04", [("B", 70)]),
        ("7", "RJ", "delivered", "2020-01-01", "2020-02-04", [("A", 5)]),
    ]
    for oid, state, status, purchase, delivered, items in cases:
        connection.execute(orders.insert(), dict(order_id=oid, customer_id=state, order_status=status, order_purchase_timestamp=datetime.fromisoformat(purchase), order_estimated_delivery_date=datetime(2020, 2, 3), order_delivered_customer_date=datetime.fromisoformat(delivered) if delivered else None))
        connection.execute(order_items.insert(), [dict(order_id=oid, order_item_id=i, seller_id=s, product_id="P", shipping_limit_date=datetime(2020, 2, 1), price=value, freight_value=99) for i, (s, value) in enumerate(items, 1)])
    connection.execute(orders.update().where(orders.c.order_id == "1").values(order_delivered_carrier_date=datetime(2020, 2, 1, 23, 59, 59)))
    connection.execute(orders.update().where(orders.c.order_id == "2").values(order_delivered_carrier_date=datetime(2019, 12, 31)))
    for rid, oid, score in [("R1", "1", 1), ("R2", "1", 5), ("R3", "2", 3)]:
        connection.execute(order_reviews.insert(), dict(review_id=rid, order_id=oid, review_score=score, review_creation_date=datetime(2020, 2, 4), review_answer_timestamp=datetime(2020, 2, 5)))


def dataset_fingerprint(connection):
    digest = hashlib.sha256()
    for table in sorted(metadata.tables.values(), key=lambda t: t.fullname):
        digest.update(table.fullname.encode())
        for row in connection.execute(select(table).order_by(*table.primary_key.columns)).mappings():
            digest.update(json.dumps(dict(row), sort_keys=True, default=str, ensure_ascii=False).encode())
    return digest.hexdigest()


def set_long_delay(connection, enabled):
    connection.execute(orders.update().where(orders.c.order_id == "6").values(order_delivered_customer_date=datetime(2020, 2, 13 if enabled else 4)))
