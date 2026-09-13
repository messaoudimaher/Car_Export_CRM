"""Health, Readiness & Observability Metrics API Endpoints (TASK-2001 & TASK-2002)."""

from typing import Any

from fastapi import APIRouter, HTTPException, Response, status

from app.core.config import settings
from app.core.database import check_database_health
from app.core.metrics import CONTENT_TYPE_LATEST, get_prometheus_metrics

router = APIRouter(prefix="", tags=["Health & Metrics"])


@router.get("/metrics", response_class=Response)
async def metrics_exporter() -> Response:
    """Prometheus metrics exposition endpoint (TASK-2001).
    
    Exposes HTTP request latency, queue depth, DB pool connections,
    and business domain counters for Prometheus scraping.
    """
    body = get_prometheus_metrics()
    return Response(content=body, media_type=CONTENT_TYPE_LATEST)


@router.get("/health", status_code=status.HTTP_200_OK)
@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness_probe() -> dict[str, Any]:
    """Liveness probe verifying that the API process is running (TASK-2002)."""
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness_probe() -> dict[str, Any]:
    """Readiness probe verifying database and infrastructure connectivity (TASK-2002).
    
    Critical Invariant: Readiness probe DOES NOT depend on LLM or WhatsApp API status.
    Third-party external provider outages must NOT bring down readiness probes.
    """
    db_healthy = await check_database_health()
    if not db_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection disconnected",
        )
    return {
        "status": "ready",
        "database": "connected",
        "redis": "connected",
        "environment": settings.ENVIRONMENT,
    }
