FROM ghcr.io/astral-sh/uv:0.12.5 AS uv
FROM python:3.12-slim

COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable \
    && useradd --create-home --uid 10001 appuser

COPY alembic.ini ./
COPY migrations ./migrations
USER appuser
EXPOSE 10000

# Um worker: os limites de execução são locais ao processo.
# Migrações e CSVs são executados separadamente, não no cold start.
CMD ["sh", "-c", "exec uvicorn intelligent_marketplace.main:app --host 0.0.0.0 --port \"${PORT:-10000}\" --workers 1"]
