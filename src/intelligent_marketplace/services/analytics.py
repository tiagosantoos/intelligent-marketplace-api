"""Contratos e definições dos primeiros indicadores históricos."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from intelligent_marketplace.infrastructure.analytics_queries import (
    delivery_by_state_query,
    seller_sales_query,
)


class DateRange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.start_date is not None and self.end_date is not None and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class SellerSalesFilter(DateRange):
    sort_by: Literal["order_count", "item_count", "item_revenue"] = "order_count"
    limit: int = Field(default=10, ge=1, le=50)


class DeliveryStateFilter(DateRange):
    sort_by: Literal["late_order_count", "late_rate_percent"] = "late_order_count"
    min_delivered_orders: int = Field(default=1, ge=1)
    limit: int = Field(default=10, ge=1, le=50)


class SellerSales(BaseModel):
    seller_id: str
    seller_state: str
    seller_city: str
    order_count: int
    item_count: int
    item_revenue: Decimal


class DeliveryState(BaseModel):
    destination_state: str
    delivered_order_count: int
    late_order_count: int
    late_rate_percent: Decimal


class SellerSalesReport(BaseModel):
    source: str = "historical.orders, historical.order_items, historical.sellers"
    definition: str = (
        "Pedidos com status delivered e itens registrados; pedidos distintos por vendedor, "
        "quantidade de itens e soma dos preços dos itens em BRL, sem frete. "
        "Não representa lucro nem faturamento fiscal. Um pedido pode contar para vários vendedores."
    )
    filters: SellerSalesFilter
    data: list[SellerSales]


class DeliveryStateReport(BaseModel):
    source: str = "historical.orders, historical.customers"
    definition: str = (
        "Estado de destino do cliente. Pedidos delivered com datas de entrega e previsão. "
        "Atraso quando a data de calendário da entrega supera a prevista; "
        "taxa = pedidos atrasados / pedidos elegíveis do estado * 100. "
        "Filtros temporais usam a data da compra, inclusive os limites informados."
    )
    filters: DeliveryStateFilter
    data: list[DeliveryState]


def seller_sales(session: Session, filters: SellerSalesFilter) -> SellerSalesReport:
    rows = session.execute(seller_sales_query(**filters.model_dump())).mappings().all()
    return SellerSalesReport(filters=filters, data=[SellerSales.model_validate(row) for row in rows])


def delivery_by_state(session: Session, filters: DeliveryStateFilter) -> DeliveryStateReport:
    rows = session.execute(delivery_by_state_query(**filters.model_dump())).mappings().all()
    return DeliveryStateReport(filters=filters, data=[DeliveryState.model_validate(row) for row in rows])
