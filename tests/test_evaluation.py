import subprocess
import sys
from decimal import Decimal

import pytest

from test_importing import postgres_import_connection
from intelligent_marketplace.evaluation.cases import CASES, BACKEND_CASES
from intelligent_marketplace.evaluation.dataset import validate_evaluation_url, seed_dataset, prepare_database, set_long_delay, dataset_fingerprint
from intelligent_marketplace.services.analysis_plan import AnalysisPlan, analyze_marketplace


@pytest.mark.parametrize("url", [
    "postgresql+psycopg://u:private-password@127.0.0.1/marketplace",
    "postgresql+psycopg://u:private-password@external.example/marketplace_eval",
    "sqlite:///marketplace_eval", "not-a-url",
])
def test_evaluation_refuses_normal_or_remote_database_without_echoing_credentials(url):
    with pytest.raises(ValueError) as error:
        validate_evaluation_url(url)
    assert "private-password" not in str(error.value)


def test_evaluation_requires_explicit_paid_execution_flag():
    result = subprocess.run([sys.executable, "scripts/evaluate_executive.py"], capture_output=True, text=True)
    assert result.returncode == 2
    assert "--allow-openai" in result.stdout


def test_evaluation_case_catalog_separates_model_and_backend():
    assert len({case.case_id for case in CASES}) == 14
    assert {case.case_id for case in CASES}.isdisjoint(BACKEND_CASES)
    assert len(CASES) + len(BACKEND_CASES) == 18


@pytest.mark.integration
def test_evaluation_seed_and_variant_match_expected_metrics(postgres_import_connection):
    from sqlalchemy.orm import Session

    connection = postgres_import_connection
    with pytest.raises(ValueError, match="banco vazio"):
        prepare_database(connection)
    seed_dataset(connection)
    initial = dataset_fingerprint(connection)
    with Session(bind=connection) as session:
        plan = AnalysisPlan(domain="delivery", metrics=["late_order_count", "late_rate_percent"], sort_by="late_order_count")
        global_row = analyze_marketplace(session, plan).data[0]
        assert (global_row["order_count"], global_row["late_order_count"], global_row["late_rate_percent"]) == (5, 3, Decimal("60"))
        set_long_delay(connection, True)
        long_plan = AnalysisPlan(domain="delivery", group_by=["seller_id"], metrics=["max_late_days"], sort_by="max_late_days")
        assert analyze_marketplace(session, long_plan).data[0]["seller_id"] == "B"
        set_long_delay(connection, False)
        review_plan = AnalysisPlan(domain="reviews", group_by=["seller_id"], metrics=["review_count", "low_review_count"], sort_by="low_review_count")
        assert analyze_marketplace(session, review_plan).data[0]["review_count"] == 3
    assert dataset_fingerprint(connection) == initial
