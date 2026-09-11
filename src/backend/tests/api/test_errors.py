"""API Integration Tests for RFC 7807 Problem Details Error Envelopes (ADR 0008)."""

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.errors import NotFoundException

# Register routes for testing exception handlers (prefix router without 'test_' name)
error_test_router = APIRouter(prefix="/api/v1/test-errors", tags=["Test Errors"])


@error_test_router.get("/not-found")
async def trigger_not_found() -> None:
    raise NotFoundException("Target customer entity was not found.")


@error_test_router.get("/unhandled-error")
async def trigger_unhandled_error() -> None:
    raise RuntimeError("Database connection string contains invalid secret token!")


@pytest.mark.asyncio
async def test_rfc7807_404_not_found_envelope(client: AsyncClient, app: FastAPI) -> None:
    """Verify 404 error returns application/problem+json RFC 7807 structure."""
    app.include_router(error_test_router)

    response = await client.get("/api/v1/test-errors/not-found")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"

    data = response.json()
    assert data["type"] == "https://errors.carexportcrm.com/not-found"
    assert data["title"] == "Resource Not Found"
    assert data["status"] == 404
    assert data["detail"] == "Target customer entity was not found."
    assert data["instance"] == "/api/v1/test-errors/not-found"
    assert "correlation_id" in data


@pytest.mark.asyncio
async def test_rfc7807_500_unhandled_exception_envelope_masks_stack_trace(
    app: FastAPI,
) -> None:
    """Verify 500 error returns RFC 7807 envelope without leaking internal stack traces."""
    app.include_router(error_test_router)

    # Use AsyncClient with raise_app_exceptions=False to capture HTTP 500 responses
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as unhandled_client:
        response = await unhandled_client.get("/api/v1/test-errors/unhandled-error")
        assert response.status_code == 500
        assert response.headers["content-type"] == "application/problem+json"

        data = response.json()
        assert data["type"] == "https://errors.carexportcrm.com/internal-error"
        assert data["title"] == "Internal Server Error"
        assert data["status"] == 500
        assert data["detail"] == "An unexpected server error occurred. Please contact support."
        assert "correlation_id" in data
        # Ensure sensitive internal error message/stack trace is masked from response body
        assert "invalid secret token" not in response.text
