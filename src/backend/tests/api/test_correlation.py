"""API Integration Tests for Correlation Middleware & Header Propagation."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_middleware_generates_correlation_id_when_missing(
    client: AsyncClient,
) -> None:
    """Verify middleware generates UUID correlation ID and duration headers when missing."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert "X-Correlation-ID" in response.headers
    assert "X-Process-Time-MS" in response.headers

    # Verify generated header is a valid UUID
    corr_id = response.headers["X-Correlation-ID"]
    parsed_uuid = uuid.UUID(corr_id)
    assert parsed_uuid is not None


@pytest.mark.asyncio
async def test_middleware_preserves_client_correlation_id(
    client: AsyncClient,
) -> None:
    """Verify custom client X-Correlation-ID is preserved across request lifecycle."""
    custom_id = "client-trace-id-9988776655"
    response = await client.get("/api/v1/health", headers={"X-Correlation-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == custom_id


@pytest.mark.asyncio
async def test_middleware_process_time_header_format(client: AsyncClient) -> None:
    """Verify X-Process-Time-MS is present and a valid numeric float."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    duration_str = response.headers["X-Process-Time-MS"]
    duration = float(duration_str)
    assert duration >= 0.0
