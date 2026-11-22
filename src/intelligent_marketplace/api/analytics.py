"""Consultas históricas de leitura com definições de métricas explícitas."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from intelligent_marketplace.infrastructure.database import get_analytics_session
from intelligent_marketplace.services.analysis_plan import AnalysisPlan, AnalysisReport, analyze_marketplace
from intelligent_marketplace.services.analytics import (
    DeliveryStateFilter,
    DeliveryStateReport,
    SellerSalesFilter,
    SellerSalesReport,
    delivery_by_state,
    seller_sales,
)

router = APIRouter(
    prefix="/api/v1/analytics", tags=["Analytics"],
    responses={503: {"description": "Banco não configurado ou consulta indisponível"}},
)
ReadSession = Annotated[Session, Depends(get_analytics_session)]


@router.post("/query", response_model=AnalysisReport, summary="Executar um plano analítico")
def query(plan: AnalysisPlan, session: ReadSession):
    """Combina dimensões, métricas e filtros, sem aceitar SQL do cliente."""
    return analyze_marketplace(session, plan)


@router.get("/sellers", response_model=SellerSalesReport, summary="Consultar vendas por vendedor")
def sellers(filters: Annotated[SellerSalesFilter, Query()], session: ReadSession):
    """Ordena por pedidos, itens ou soma dos preços. Datas filtram a compra."""
    return seller_sales(session, filters)


@router.get("/delivery-by-state", response_model=DeliveryStateReport, summary="Consultar atrasos por estado de destino")
def states(filters: Annotated[DeliveryStateFilter, Query()], session: ReadSession):
    """Distingue quantidade e taxa de atraso e informa o denominador por estado."""
    return delivery_by_state(session, filters)
