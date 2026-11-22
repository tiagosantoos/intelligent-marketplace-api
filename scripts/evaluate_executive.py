"""Avaliação real explícita: uv run python scripts/evaluate_executive.py --help."""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

import httpx
from pydantic import SecretStr

from intelligent_marketplace.core.config import Settings
from intelligent_marketplace.evaluation.cases import CASES, BACKEND_CASES
from intelligent_marketplace.evaluation.dataset import (
    DATASET_VERSION, dataset_fingerprint, prepare_database, set_long_delay, validate_evaluation_url,
)
from intelligent_marketplace.infrastructure.database import Database
from intelligent_marketplace.main import create_app


def write_report(path, report):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


async def evaluate(args):
    if not args.allow_openai:
        raise ValueError("Use --allow-openai para executar chamadas reais com custo na conta configurada")
    url = os.environ.get("EVALUATION_DATABASE_URL", "")
    validate_evaluation_url(url)
    settings = Settings()
    if settings.openai_api_key is None or settings.openai_model is None:
        raise ValueError("Configure OPENAI_API_KEY e OPENAI_MODEL no .env")
    settings = settings.model_copy(update={"database_url": SecretStr(url), "app_env": "test"})
    requested = set(args.cases.split(",")) if args.cases else {c.case_id for c in CASES}
    if not requested <= {c.case_id for c in CASES}:
        raise ValueError("Selecione apenas IDs de cenários de linguagem natural existentes")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"{run_id}.json"
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    source = Path("src/intelligent_marketplace")
    hashes = {str(p.as_posix()): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.rglob("*.py"))}
    report = {
        "run_id": run_id, "commit": commit, "working_tree_dirty": dirty,
        "source_sha256": hashes, "model": settings.openai_model,
        "dataset_version": DATASET_VERSION, "data_classification": "synthetic_only",
        "repetitions": 1, "reviewer": None, "cases": [],
        "backend_cases": {key: {"result": "not_run_by_this_command", "verification": value} for key, value in BACKEND_CASES.items()},
        "limitations": ["Uma execução por pergunta não comprova confiabilidade estatística.", "HTTP 200 não significa aprovação sem revisão de resposta e evidências.", "Tokens e custo não são medidos por este comando.", "O identificador configurado pode ser um alias de modelo."],
    }
    database = Database(settings)
    try:
        with database.engine.begin() as connection:
            prepare_database(connection)
            report["dataset_sha256_before"] = dataset_fingerprint(connection)
        write_report(path, report)
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://evaluation") as client:
                for case in CASES:
                    if case.case_id not in requested:
                        continue
                    with database.engine.begin() as connection:
                        set_long_delay(connection, case.variant == "long_delay")
                    started = monotonic()
                    record = {"case_id": case.case_id, "question": case.question, "expected": case.expected, "dataset_variant": case.variant, "executed_at": datetime.now(timezone.utc).isoformat(), "result": "needs_review", "reviewer": None}
                    try:
                        # O gabarito fica somente no relatório, nunca no input do agente.
                        response = await client.post("/api/v1/executive/messages", json={"question": case.question})
                        record.update(http_status=response.status_code, response=response.json())
                        if response.status_code != 200:
                            record.update(result="failed", failure_reason="HTTP não retornou 200; examinar erro sanitizado")
                        secret = settings.openai_api_key.get_secret_value()
                        serialized = json.dumps(record, ensure_ascii=False)
                        if secret in serialized:
                            record = json.loads(serialized.replace(secret, "[REDACTED]"))
                            record.update(result="failed", failure_reason="Credencial encontrada e removida do registro")
                    finally:
                        with database.engine.begin() as connection:
                            set_long_delay(connection, False)
                    record["duration_seconds"] = round(monotonic() - started, 3)
                    report["cases"].append(record)
                    write_report(path, report)
                    print(f"{case.case_id}: HTTP {record.get('http_status')} / {record['result']}", flush=True)
        with database.engine.connect() as connection:
            report["dataset_sha256_after"] = dataset_fingerprint(connection)
        report["dataset_unchanged"] = report["dataset_sha256_before"] == report["dataset_sha256_after"]
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_report(path, report)
        print(f"Relatorio: {path.as_posix()}", flush=True)
        return 0 if report["dataset_unchanged"] and all(c["http_status"] == 200 for c in report["cases"]) else 1
    finally:
        database.dispose()


def main():
    parser = argparse.ArgumentParser(description="Avalia o Executivo em banco local vazio terminado em _eval, somente com dados sintéticos")
    parser.add_argument("--allow-openai", action="store_true", help="Executar chamadas reais que consomem créditos")
    parser.add_argument("--cases", help="IDs separados por vírgula; padrão: os 14 cenários de linguagem natural")
    parser.add_argument("--output-dir", default="data/evaluations", help="Pasta dos relatórios incrementais JSON")
    args = parser.parse_args()
    try:
        return asyncio.run(evaluate(args))
    except ValueError as error:
        print(str(error))
        return 2
    except Exception as error:
        # Não imprimir repr de exceções de driver/provedor que possam conter segredos.
        print(f"Avaliação interrompida ({type(error).__name__}); consulte o relatório parcial, se criado.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
