from __future__ import annotations

import logging
from secrets import token_urlsafe

from fastapi import FastAPI, Request

from src.app.infrastructure.request_debug import (
    bind_request_debug_context,
    current_debug_ref,
    reset_request_debug_context,
)

logger = logging.getLogger(__name__)


def install_request_debug_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_debug_context_middleware(request: Request, call_next):
        correlation_seed = request.headers.get("x-correlation-id") or request.headers.get(
            "x-request-id"
        )
        correlation_id = correlation_seed or f"corr:req:{token_urlsafe(8)}"
        debug_ref = f"debug:req:{token_urlsafe(8)}"
        binding = bind_request_debug_context(
            correlation_id=correlation_id,
            debug_ref=debug_ref,
        )
        logger.info(
            "Handling request path=%s method=%s",
            request.url.path,
            request.method,
        )
        try:
            response = await call_next(request)
            response.headers["X-Debug-Ref"] = current_debug_ref()
            return response
        finally:
            reset_request_debug_context(binding)
