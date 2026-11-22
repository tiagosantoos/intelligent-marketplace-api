from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from test_importing import postgres_import_connection
from test_analytics import analytics_session
from intelligent_marketplace.infrastructure.models.historical import order_reviews, orders, products
from intelligent_marketplace.services.analysis_plan import AnalysisPlan, analyze_marketplace


@pytest.mark.parametrize("changes", [
    {"metrics": ["item_revenue"], "sort_by": "item_revenue"},
    {"sort_by": "avg_late_days"}, {"group_by": ["seller_id", "seller_id"]},
    {"group_by": ["seller_id", "destination_state", "purchase_month"]},
    {"group_by": ["sql_column"]}, {"sql": "DROP TABLE historical.orders"},
    {"order_status": "canceled"}, {"limit": 1000},
    {"start_date": "2020-02-01", "end_date": "2020-01-01"},
])
def test_invalid_analysis_plan(changes):
    with pytest.raises(ValidationError):
        AnalysisPlan(**({"domain": "delivery", "metrics": ["late_order_count"], "sort_by": "late_order_count"} | changes))


def delivery_plan(**kwargs):
    return AnalysisPlan(**({"domain": "delivery", "group_by": ["seller_id"], "metrics": ["late_order_count", "late_rate_percent", "avg_late_days", "max_late_days", "total_late_days"], "sort_by": "late_order_count"} | kwargs))


@pytest.mark.integration
def test_delays_by_seller_do_not_duplicate_multi_item_orders(analytics_session):
    report = analyze_marketplace(analytics_session, delivery_plan())
    a, b = report.data
    assert (a["seller_id"], a["order_count"], a["late_order_count"], a["late_rate_percent"]) == ("A", 3, 2, Decimal("66.67"))
    assert (a["avg_late_days"], a["max_late_days"], a["total_late_days"]) == (Decimal("1"), 1, 2)
    assert (b["order_count"], b["late_order_count"]) == (3, 1)
    assert "responsabilidade individual" in report.definition
    assert analyze_marketplace(analytics_session, delivery_plan(min_order_count=4)).data == []


@pytest.mark.integration
def test_duration_and_volume_rankings_can_differ(analytics_session):
    analytics_session.execute(orders.update().where(orders.c.order_id == "6").values(order_delivered_customer_date=datetime(2020, 2, 13)))
    largest = analyze_marketplace(analytics_session, delivery_plan(sort_by="max_late_days", limit=1)).data[0]
    assert (largest["seller_id"], largest["max_late_days"], largest["late_order_count"]) == ("B", 10, 1)
    volume = analyze_marketplace(analytics_session, delivery_plan(limit=1)).data[0]
    assert volume["seller_id"] == "A"


@pytest.mark.integration
def test_global_and_cross_dimensions_filters_and_empty_results(analytics_session):
    global_report = analyze_marketplace(analytics_session, delivery_plan(group_by=[]))
    assert (global_report.data[0]["order_count"], global_report.data[0]["late_order_count"]) == (5, 3)
    cross = analyze_marketplace(analytics_session, delivery_plan(group_by=["seller_id", "destination_state"], seller_id="A", destination_state="RJ", end_date="2020-01-31"))
    assert cross.data[0]["order_count"] == 2
    assert cross.data[0]["late_rate_percent"] == Decimal("100")
    assert analyze_marketplace(analytics_session, delivery_plan(seller_id="' OR 1=1 --")).data == []
    on_time = analyze_marketplace(analytics_session, delivery_plan(destination_state="SP"))
    assert all(row["avg_late_days"] is None for row in on_time.data)


@pytest.mark.integration
def test_sales_by_category_and_month_preserve_item_values(analytics_session):
    analytics_session.execute(products.update().values(product_category_name="category"))
    plan = AnalysisPlan(domain="sales", group_by=["product_category", "purchase_month"], metrics=["item_count", "item_revenue"], sort_by="item_revenue")
    report = analyze_marketplace(analytics_session, plan)
    assert report.data[0] == {"product_category": "category", "purchase_month": "2020-01", "order_count": 5, "item_count": 7, "item_revenue": Decimal("235")}
    canceled = analyze_marketplace(analytics_session, AnalysisPlan(domain="sales", metrics=["item_revenue"], sort_by="item_revenue", order_status="canceled"))
    assert canceled.data[0]["item_revenue"] == Decimal("1000")


@pytest.mark.integration
def test_reviews_by_seller_preserve_review_grain(analytics_session):
    for rid, oid, score in [("R1", "1", 1), ("R2", "1", 5), ("R3", "2", 3)]:
        analytics_session.execute(order_reviews.insert(), {"review_id": rid, "order_id": oid, "review_score": score, "review_creation_date": datetime(2020, 2, 4), "review_answer_timestamp": datetime(2020, 2, 5)})
    plan = AnalysisPlan(domain="reviews", group_by=["seller_id"], metrics=["review_count", "avg_review_score", "low_review_count", "low_review_rate_percent"], sort_by="low_review_count")
    a = analyze_marketplace(analytics_session, plan).data[0]
    assert (a["seller_id"], a["order_count"], a["review_count"]) == ("A", 2, 3)
    assert (a["avg_review_score"], a["low_review_count"], a["low_review_rate_percent"]) == (Decimal("3"), 2, Decimal("66.67"))


@pytest.mark.integration
def test_dispatch_duration_is_order_level_and_excludes_invalid_dates(analytics_session):
    analytics_session.execute(orders.update().where(orders.c.order_id == "1").values(order_delivered_carrier_date=datetime(2020, 2, 1, 23, 59, 59)))
    analytics_session.execute(orders.update().where(orders.c.order_id == "2").values(order_delivered_carrier_date=datetime(2019, 12, 31)))
    plan = AnalysisPlan(domain="dispatch", group_by=["seller_id"], metrics=["avg_dispatch_days", "max_dispatch_days"], sort_by="avg_dispatch_days")
    report = analyze_marketplace(analytics_session, plan)
    assert len(report.data) == 2
    assert all(row["order_count"] == 1 and row["avg_dispatch_days"] == Decimal("1") for row in report.data)
