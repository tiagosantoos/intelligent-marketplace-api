from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from test_importing import postgres_import_connection
from intelligent_marketplace.infrastructure.database import Database, get_analytics_session
from intelligent_marketplace.core.config import Settings
from intelligent_marketplace.infrastructure.models.historical import customers, sellers, products, orders, order_items
from intelligent_marketplace.main import create_app
from intelligent_marketplace.services.analytics import SellerSalesFilter, DeliveryStateFilter, seller_sales, delivery_by_state


@pytest.mark.anyio
async def test_analytics_without_database(app_settings):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(app_settings)), base_url="http://test") as client:
        assert (await client.get("/api/v1/analytics/sellers")).status_code == 503
        assert (await client.get("/api/v1/analytics/delivery-by-state")).status_code == 503
        assert (await client.get("/health")).status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize("query", ["limit=51", "sort_by=sql", "start_date=2020-02-01&end_date=2020-01-01", "unexpected=x"])
async def test_invalid_query_is_rejected(app_settings, query):
    app = create_app(app_settings)
    app.dependency_overrides[get_analytics_session] = lambda: None
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/analytics/sellers?{query}")
    assert response.status_code == 422


@pytest.fixture
def analytics_session(postgres_import_connection):
    connection = postgres_import_connection
    connection.execute(customers.insert(), [dict(customer_id=state, customer_unique_id=state, customer_zip_code_prefix="01001", customer_city="city", customer_state=state) for state in ("SP", "RJ", "AL")])
    connection.execute(sellers.insert(), [dict(seller_id=s, seller_zip_code_prefix="01001", seller_city="city", seller_state="SP") for s in ("A", "B")])
    connection.execute(products.insert(), {"product_id": "P"})
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
    with Session(bind=connection) as session:
        yield session


@pytest.mark.integration
def test_sales_preserve_seller_grain_and_revenue(analytics_session):
    report = seller_sales(analytics_session, SellerSalesFilter())
    a, b = report.data
    assert (a.seller_id, a.order_count, a.item_count, a.item_revenue) == ("A", 4, 5, Decimal("135"))
    assert (b.seller_id, b.order_count, b.item_count, b.item_revenue) == ("B", 3, 3, Decimal("150"))
    assert seller_sales(analytics_session, SellerSalesFilter(sort_by="item_revenue", limit=1)).data[0].seller_id == "B"
    january = seller_sales(analytics_session, SellerSalesFilter(end_date="2020-01-31"))
    assert january.data[1].item_revenue == Decimal("100")
    assert seller_sales(analytics_session, SellerSalesFilter(start_date="2030-01-01")).data == []
    assert report.model_dump(mode="json")["data"][0]["item_revenue"] == "135.00"


@pytest.mark.integration
def test_delivery_calendar_dates_and_denominators(analytics_session):
    report = delivery_by_state(analytics_session, DeliveryStateFilter())
    assert [(r.destination_state, r.delivered_order_count, r.late_order_count, r.late_rate_percent) for r in report.data] == [("RJ", 3, 2, Decimal("66.67")), ("AL", 1, 1, Decimal("100")), ("SP", 1, 0, Decimal("0"))]
    assert delivery_by_state(analytics_session, DeliveryStateFilter(sort_by="late_rate_percent")).data[0].destination_state == "AL"
    assert [r.destination_state for r in delivery_by_state(analytics_session, DeliveryStateFilter(min_delivered_orders=2)).data] == ["RJ"]
    january = delivery_by_state(analytics_session, DeliveryStateFilter(end_date="2020-01-31"))
    assert january.data[0].late_rate_percent == Decimal("100")


@pytest.mark.integration
def test_real_session_is_read_only_and_has_timeout(app_settings):
    import os
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Defina TEST_DATABASE_URL")
    settings = Settings(_env_file=None, database_url=url, analytics_query_timeout_seconds=3)
    database = Database(settings)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(database=database, settings=settings)))
    generator = get_analytics_session(request)
    try:
        session = next(generator)
        assert session.scalar(text("SHOW transaction_read_only")) == "on"
        assert session.scalar(text("SHOW statement_timeout")) == "3s"
        with pytest.raises(SQLAlchemyError) as error:
            session.execute(text("CREATE TABLE public.analytics_write_forbidden (id integer)"))
        with pytest.raises(HTTPException) as http_error:
            generator.throw(error.value)
        assert http_error.value.status_code == 503
        assert http_error.value.detail == "Analytics are temporarily unavailable"
    finally:
        generator.close()
        database.dispose()
