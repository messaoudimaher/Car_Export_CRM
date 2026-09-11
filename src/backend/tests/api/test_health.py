"""API Integration Tests for Health Endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness_probe_endpoint(client: AsyncClient) -> None:
    """Verify GET /api/v1/health returns 200 OK with expected payload."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "environment" in data
    assert "X-Correlation-ID" in response.headers


@pytest.mark.asyncio
async def test_correlation_id_header_propagation(client: AsyncClient) -> None:
    """Verify custom X-Correlation-ID header is propagated through response headers."""
    custom_corr_id = "test-corr-id-99999"
    response = await client.get("/api/v1/health", headers={"X-Correlation-ID": custom_corr_id})
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == custom_corr_id
