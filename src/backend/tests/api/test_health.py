"""API Integration Tests for Health & Prometheus Metrics Endpoints (TASK-2001 & TASK-2002)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness_probe_endpoint(client: AsyncClient) -> None:
    """Verify GET /api/v1/health returns 200 OK with expected payload (TASK-2002)."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "environment" in data
    assert "X-Correlation-ID" in response.headers


@pytest.mark.asyncio
async def test_prometheus_metrics_exporter_endpoint(client: AsyncClient) -> None:
    """Verify GET /metrics returns 200 OK with Prometheus exposition format (TASK-2001)."""
    # Trigger a request first to record metrics
    await client.get("/api/v1/health")

    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")

    content = response.text
    assert "http_requests_total" in content
    assert "http_request_duration_seconds" in content
    assert "db_pool_connections_active" in content
    assert "whatsapp_messages_ingested_total" in content


@pytest.mark.asyncio
async def test_readiness_probe_failure_isolation(client: AsyncClient) -> None:
    """Verify GET /health/ready returns status and isolated third-party health (TASK-2002)."""
    response = await client.get("/health/ready")
    assert response.status_code in (200, 503)
    if response.status_code == 200:
        data = response.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"
        assert data["redis"] == "connected"
