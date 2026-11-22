"""Compila planos validados em SQL parametrizado com o grão correto por domínio."""

from decimal import Decimal

import sqlalchemy as sa

from intelligent_marketplace.infrastructure.analytics_queries import date_filters
from intelligent_marketplace.infrastructure.models.historical import customers, orders, order_items, sellers, products, order_reviews


def build_analysis_query(plan):
    dimensions = {
        "seller_id": sellers.c.seller_id,
        "seller_state": sellers.c.seller_state,
        "destination_state": customers.c.customer_state,
        "product_category": products.c.product_category_name,
        "purchase_month": sa.func.to_char(orders.c.order_purchase_timestamp, "YYYY-MM"),
        "order_status": orders.c.order_status,
    }
    source_tables = ["historical.orders"]
    joined = orders
    needs_items = plan.domain == "sales" or bool(
        set(plan.group_by) & {"seller_id", "seller_state", "product_category"}
    ) or any(value is not None for value in (plan.seller_id, plan.seller_state, plan.product_category))
    if needs_items:
        joined = joined.join(order_items).join(sellers).join(products)
        source_tables += ["historical.order_items", "historical.sellers", "historical.products"]
    if "destination_state" in plan.group_by or plan.destination_state is not None:
        joined = joined.join(customers)
        source_tables.append("historical.customers")

    filters = date_filters(plan.start_date, plan.end_date)
    default_status = "delivered" if plan.domain in ("delivery", "sales") else None
    status = plan.order_status or default_status
    if status is not None:
        filters.append(orders.c.order_status == status)
    for value, column in (
        (plan.seller_id, sellers.c.seller_id), (plan.seller_state, sellers.c.seller_state),
        (plan.product_category, products.c.product_category_name),
        (plan.destination_state, customers.c.customer_state),
    ):
        if value is not None:
            filters.append(column == value)

    selected = [orders.c.order_id]
    selected += [dimensions[name].label(name) for name in plan.group_by]
    if plan.domain == "sales":
        selected += [order_items.c.order_item_id, order_items.c.price]
    elif plan.domain == "delivery":
        filters += [orders.c.order_delivered_customer_date.is_not(None), orders.c.order_estimated_delivery_date.is_not(None)]
        selected += [sa.func.greatest(
            sa.cast(orders.c.order_delivered_customer_date, sa.Date) - sa.cast(orders.c.order_estimated_delivery_date, sa.Date), 0,
        ).label("late_days")]
    elif plan.domain == "dispatch":
        filters += [orders.c.order_delivered_carrier_date >= orders.c.order_purchase_timestamp]
        selected += [(sa.extract("epoch", orders.c.order_delivered_carrier_date - orders.c.order_purchase_timestamp) / Decimal("86400")).label("dispatch_days")]
    else:
        joined = joined.join(order_reviews)
        source_tables.append("historical.order_reviews")
        selected += [order_reviews.c.review_id, order_reviews.c.review_score]

    # Remove a multiplicação por itens antes de calcular medidas de pedidos/avaliações.
    cohort = sa.select(*selected).select_from(joined).where(*filters).distinct().cte("cohort")
    order_count = sa.func.count(sa.distinct(cohort.c.order_id))
    metrics = {"order_count": order_count}
    if plan.domain == "sales":
        metrics.update(item_count=sa.func.count(), item_revenue=sa.func.sum(cohort.c.price))
    elif plan.domain == "delivery":
        late_count = sa.func.coalesce(sa.func.sum(sa.case((cohort.c.late_days > 0, 1), else_=0)), 0)
        metrics.update(
            late_order_count=late_count,
            late_rate_percent=sa.func.round(late_count * Decimal("100") / sa.func.nullif(order_count, 0), 2),
            avg_late_days=sa.func.round(sa.func.avg(sa.func.nullif(cohort.c.late_days, 0)), 2),
            max_late_days=sa.func.max(cohort.c.late_days),
            total_late_days=sa.func.coalesce(sa.func.sum(cohort.c.late_days), 0),
        )
    elif plan.domain == "reviews":
        review_count = sa.func.count()
        low_count = sa.func.coalesce(sa.func.sum(sa.case((cohort.c.review_score.between(1, 3), 1), else_=0)), 0)
        metrics.update(
            review_count=review_count, avg_review_score=sa.func.round(sa.func.avg(cohort.c.review_score), 2),
            low_review_count=low_count,
            low_review_rate_percent=sa.func.round(low_count * Decimal("100") / sa.func.nullif(review_count, 0), 2),
        )
    else:
        metrics.update(avg_dispatch_days=sa.func.round(sa.func.avg(cohort.c.dispatch_days), 2), max_dispatch_days=sa.func.round(sa.func.max(cohort.c.dispatch_days), 2))

    group_columns = [cohort.c[name] for name in plan.group_by]
    output_metrics = list(dict.fromkeys(["order_count", *plan.metrics]))
    query = sa.select(*group_columns, *[metrics[name].label(name) for name in output_metrics]).select_from(cohort)
    if group_columns:
        query = query.group_by(*group_columns)
    query = query.having(order_count >= plan.min_order_count)
    sort_expression = metrics[plan.sort_by]
    query = query.order_by(
        (sort_expression.desc() if plan.sort_direction == "desc" else sort_expression.asc()).nulls_last(),
        *[column.asc().nulls_last() for column in group_columns],
    ).limit(plan.limit)
    return query, ", ".join(source_tables)
