"""Prometheus HTTP Metrics Middleware (TASK-2001 / WS-20)."""

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.metrics import record_http_request


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware recording HTTP request counts and latency histograms for Prometheus."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Skip internal metrics endpoint scraping to avoid metric feedback loops
        if request.url.path == "/metrics":
            return await call_next(request)

        start_time = time.perf_counter()
        response: Response = await call_next(request)
        duration_seconds = time.perf_counter() - start_time

        # Record HTTP request metrics
        record_http_request(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
            duration_seconds=duration_seconds,
        )

        return response
