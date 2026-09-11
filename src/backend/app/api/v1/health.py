"""Health & Readiness API Endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.core.database import check_database_health

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", status_code=status.HTTP_200_OK)
async def liveness_probe() -> dict[str, Any]:
    """Liveness probe verifying that the API process is running."""
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_probe() -> dict[str, Any]:
    """Readiness probe verifying database connectivity."""
    db_healthy = await check_database_health()
    if not db_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unhealthy", "database": "disconnected"},
        )
    return {
        "status": "ready",
        "database": "connected",
        "environment": settings.ENVIRONMENT,
    }
