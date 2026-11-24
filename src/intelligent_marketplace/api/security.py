"""Controle inicial para demonstração: chave compartilhada e limites por processo."""

from collections import deque
from collections.abc import AsyncIterator
from hmac import compare_digest
from math import ceil
from time import monotonic
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

access_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(request: Request, provided: Annotated[str | None, Security(access_header)] = None):
    configured = request.app.state.settings.api_access_key
    if configured is None:
        # A configuração impede production sem chave; local permanece opcional.
        return
    if provided is None or not compare_digest(provided.encode(), configured.get_secret_value().encode()):
        raise HTTPException(401, "Invalid or missing API access key")


class ExecutiveLimits:
    def __init__(self, per_minute: int, max_concurrent: int):
        self.per_minute = per_minute
        self.max_concurrent = max_concurrent
        self.started: deque[float] = deque()
        self.active = 0

    def acquire(self):
        now = monotonic()
        while self.started and now - self.started[0] >= 60:
            self.started.popleft()
        if len(self.started) >= self.per_minute:
            retry = max(1, ceil(60 - (now - self.started[0])))
            raise HTTPException(429, "Executive request limit reached", headers={"Retry-After": str(retry)})
        if self.active >= self.max_concurrent:
            raise HTTPException(429, "Executive is busy", headers={"Retry-After": "1"})
        self.started.append(now)
        self.active += 1

    def release(self):
        self.active -= 1


async def protect_executive(request: Request, _: Annotated[None, Depends(require_api_key)]) -> AsyncIterator[None]:
    if request.app.state.settings.api_access_key is None:
        yield
        return
    limits = request.app.state.executive_limits
    # Aquisição/liberação no loop da aplicação, sem await entre conferir e reservar.
    limits.acquire()
    try:
        yield
    finally:
        limits.release()
