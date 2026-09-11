"""FastAPI Application Entry Point & Global Middleware."""

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.middleware.correlation import CorrelationMiddleware
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.logging import (
    configure_logging,
    correlation_id_ctx,
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

    # Global Exception Handler returning RFC 7807 compatible error envelope
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        corr_id = correlation_id_ctx.get() or str(uuid.uuid4())
        logger.error(
            "unhandled_server_error",
            extra={
                "path": request.url.path,
                "error": str(exc),
            },
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "type": "https://errors.carexportcrm.com/internal-error",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected server error occurred. Please contact support.",
                "instance": request.url.path,
                "correlation_id": corr_id,
            },
            headers={"X-Correlation-ID": corr_id},
        )

    # Include API routers
    app.include_router(api_v1_router)

    return app


app = create_app()
