"""Correlation ID & Context Tracing Middleware."""

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import (
    correlation_id_ctx,
    logger,
    tenant_id_ctx,
    user_id_ctx,
)
from app.core.uuid import generate_uuidv7


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware extracting or generating X-Correlation-ID headers and tracing context."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Extract X-Correlation-ID header or generate new UUIDv7
        correlation_id = request.headers.get("X-Correlation-ID") or str(generate_uuidv7())
        corr_token = correlation_id_ctx.set(correlation_id)
        tenant_token = tenant_id_ctx.set(None)
        user_token = user_id_ctx.set(None)

        start_time = time.perf_counter()
        try:
            response: Response = await call_next(request)
            process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Process-Time-MS"] = str(process_time_ms)

            logger.info(
                "http_request_processed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": process_time_ms,
                },
            )
            return response
        finally:
            correlation_id_ctx.reset(corr_token)
            tenant_id_ctx.reset(tenant_token)
            user_id_ctx.reset(user_token)
