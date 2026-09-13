"""FastAPI Application Entry Point & Global Middleware."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.middleware.correlation import CorrelationMiddleware
from app.api.middleware.metrics import PrometheusMetricsMiddleware
from app.api.middleware.webhook_signature import WebhookSignatureMiddleware
from app.api.v1.health import router as health_router
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import (
    configure_logging,
    logger,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifespan events."""
    configure_logging(settings.LOG_LEVEL)
    logger.info(
        "Application startup initialized",
        extra={
            "app_name": settings.APP_NAME,
            "environment": settings.ENVIRONMENT,
        },
    )
    yield
    logger.info("Application shutdown completed")


def create_app() -> FastAPI:
    """FastAPI Application Factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="Car-Export-CRM Backend Modular Monolith API Engine",
        version="0.1.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # Register Correlation ID & Context Tracing Middleware
    app.add_middleware(CorrelationMiddleware)

    # Register Prometheus HTTP Metrics Exporter Middleware (TASK-2001)
    app.add_middleware(PrometheusMetricsMiddleware)

    # Register Webhook Signature Verification Middleware (BR-007)
    app.add_middleware(WebhookSignatureMiddleware)

    # Register RFC 7807 Problem Details Exception Handlers (ADR 0008)
    register_exception_handlers(app)

    # Include API routers
    app.include_router(health_router)
    app.include_router(api_v1_router)


    return app


app = create_app()
