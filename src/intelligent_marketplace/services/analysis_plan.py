"""Plano analítico que a IA compõe; métricas e relações com significado definido."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from intelligent_marketplace.services.analytics import DateRange

Dimension = Literal["seller_id", "seller_state", "destination_state", "product_category", "purchase_month", "order_status"]
Metric = Literal[
    "order_count", "item_count", "item_revenue", "late_order_count", "late_rate_percent",
    "avg_late_days", "max_late_days", "total_late_days", "review_count", "avg_review_score",
    "low_review_count", "low_review_rate_percent", "avg_dispatch_days", "max_dispatch_days",
]
DOMAIN_METRICS = {
    "delivery": {"order_count", "late_order_count", "late_rate_percent", "avg_late_days", "max_late_days", "total_late_days"},
    "sales": {"order_count", "item_count", "item_revenue"},
    "reviews": {"order_count", "review_count", "avg_review_score", "low_review_count", "low_review_rate_percent"},
    "dispatch": {"order_count", "avg_dispatch_days", "max_dispatch_days"},
}
DEFINITIONS = {
    "delivery": (
        "Pedidos delivered com datas de entrega e previsão. Dias de atraso = data de calendário "
        "da entrega menos data prevista, limitado a zero. Taxa = atrasados / pedidos elegíveis * 100. "
        "avg_late_days considera somente pedidos atrasados; max e total usam todos os elegíveis."
    ),
    "sales": (
        "Itens dos pedidos nos status selecionados; padrão delivered. order_count conta pedidos "
        "distintos; item_count conta itens; item_revenue soma preços em BRL, sem frete. "
        "Valor dos itens não representa lucro nem faturamento fiscal."
    ),
    "reviews": (
        "Avaliações registradas, sem restrição padrão de status. review_count conta avaliações; "
        "order_count conta pedidos avaliados distintos. avg_review_score é a média por avaliação. "
        "low_review_count conta notas de 1 a 3; sua taxa usa o total de avaliações como denominador."
    ),
    "dispatch": (
        "Pedidos com despacho registrado em order_delivered_carrier_date igual ou posterior à compra. "
        "Duração em dias de 24 horas entre compra e despacho, sem restrição padrão de status. "
        "O despacho é registrado no pedido; não comprova quando cada vendedor despachou seus itens."
    ),
}


class AnalysisPlan(DateRange):
    domain: Literal["delivery", "sales", "reviews", "dispatch"]
    group_by: list[Dimension] = Field(default_factory=list, max_length=2)
    metrics: list[Metric] = Field(min_length=1, max_length=6)
    sort_by: Metric
    sort_direction: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=10, ge=1, le=50)
    min_order_count: int = Field(default=1, ge=1)
    seller_id: str | None = Field(default=None, min_length=1, max_length=32)
    destination_state: str | None = Field(default=None, pattern="^[A-Z]{2}$")
    seller_state: str | None = Field(default=None, pattern="^[A-Z]{2}$")
    product_category: str | None = Field(default=None, min_length=1, max_length=200)
    order_status: Literal["created", "approved", "invoiced", "processing", "shipped", "delivered", "unavailable", "canceled"] | None = None

    @model_validator(mode="after")
    def coherent_plan(self):
        if len(set(self.group_by)) != len(self.group_by) or len(set(self.metrics)) != len(self.metrics):
            raise ValueError("Dimensions and metrics must not be repeated")
        if not set(self.metrics) <= DOMAIN_METRICS[self.domain]:
            raise ValueError(f"Metrics are incompatible with domain {self.domain}")
        if self.sort_by not in self.metrics:
            raise ValueError("sort_by must be included in metrics")
        if self.domain == "delivery" and self.order_status not in (None, "delivered"):
            raise ValueError("Delivery analysis requires delivered orders")
        return self


class AnalysisReport(BaseModel):
    source: str
    definition: str
    plan: AnalysisPlan
    data: list[dict[str, str | int | Decimal | None]]


def analyze_marketplace(session: Session, plan: AnalysisPlan) -> AnalysisReport:
    from intelligent_marketplace.infrastructure.flexible_analytics import build_analysis_query

    query, source = build_analysis_query(plan)
    rows = session.execute(query).mappings().all()
    return AnalysisReport(
        source=source,
        definition=(
            DEFINITIONS[plan.domain] + " Datas de filtro referem-se à compra, com limites inclusivos. "
            "Cada pedido conta uma vez por grupo (cada avaliação uma vez no domínio reviews). "
            "Pedidos com múltiplos vendedores/categorias podem participar de vários grupos; "
            "não some esses grupos para obter o total global. A associação de um vendedor a um "
            "pedido atrasado ou mal avaliado não comprova responsabilidade individual. "
            "order_count é sempre incluído como denominador/amostra. Médias sem observações são nulas."
        ),
        plan=plan, data=[dict(row) for row in rows],
    )
