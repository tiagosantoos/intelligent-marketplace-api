"""Consultas agregadas e parametrizadas; nenhuma escrita ou SQL fornecido pelo cliente."""

from datetime import datetime, time
from decimal import Decimal

import sqlalchemy as sa

from intelligent_marketplace.infrastructure.models.historical import customers, order_items, orders, sellers


def date_filters(start_date, end_date):
    filters = []
    if start_date is not None:
        filters.append(orders.c.order_purchase_timestamp >= datetime.combine(start_date, time.min))
    if end_date is not None:
        filters.append(orders.c.order_purchase_timestamp <= datetime.combine(end_date, time.max))
    return filters


def seller_sales_query(*, sort_by, limit, start_date=None, end_date=None):
    order_count = sa.func.count(sa.distinct(order_items.c.order_id)).label("order_count")
    item_count = sa.func.count().label("item_count")
    revenue = sa.func.sum(order_items.c.price).label("item_revenue")
    sort_columns = {"order_count": order_count, "item_count": item_count, "item_revenue": revenue}
    return (
        sa.select(
            sellers.c.seller_id, sellers.c.seller_state, sellers.c.seller_city,
            order_count, item_count, revenue,
        )
        .select_from(order_items.join(orders).join(sellers))
        .where(orders.c.order_status == "delivered", *date_filters(start_date, end_date))
        .group_by(sellers.c.seller_id, sellers.c.seller_state, sellers.c.seller_city)
        .order_by(sort_columns[sort_by].desc(), sellers.c.seller_id.asc())
        .limit(limit)
    )


def delivery_by_state_query(*, sort_by, limit, min_delivered_orders, start_date=None, end_date=None):
    late = sa.cast(orders.c.order_delivered_customer_date, sa.Date) > sa.cast(
        orders.c.order_estimated_delivery_date, sa.Date
    )
    delivered_count = sa.func.count().label("delivered_order_count")
    late_count = sa.func.sum(sa.case((late, 1), else_=0)).label("late_order_count")
    # Sort by the unrounded rate; rounding is only for presentation.
    rate = sa.cast(late_count, sa.Numeric) * Decimal("100") / delivered_count
    sort_columns = {"late_order_count": late_count, "late_rate_percent": rate}
    return (
        sa.select(
            customers.c.customer_state.label("destination_state"), delivered_count, late_count,
            sa.func.round(rate, 2).label("late_rate_percent"),
        )
        .select_from(orders.join(customers))
        .where(
            orders.c.order_status == "delivered",
            orders.c.order_delivered_customer_date.is_not(None),
            orders.c.order_estimated_delivery_date.is_not(None),
            *date_filters(start_date, end_date),
        )
        .group_by(customers.c.customer_state)
        .having(delivered_count >= min_delivered_orders)
        .order_by(sort_columns[sort_by].desc(), late_count.desc(), customers.c.customer_state.asc())
        .limit(limit)
    )
