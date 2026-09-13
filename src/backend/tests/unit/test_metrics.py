"""Unit Tests for Prometheus Metrics Module (TASK-2001)."""

from app.core.metrics import (
    AI_EXTRACTION_ATTEMPTS_TOTAL,
    DB_POOL_CONNECTIONS_ACTIVE,
    QUOTATIONS_GENERATED_TOTAL,
    WHATSAPP_MESSAGES_INGESTED_TOTAL,
    get_prometheus_metrics,
    record_http_request,
)


def test_record_http_request_increments_counters() -> None:
    """Verify record_http_request helper increments HTTP requests total counter."""
    record_http_request(method="GET", endpoint="/api/v1/customers", status_code=200, duration_seconds=0.045)
    metrics_output = get_prometheus_metrics().decode("utf-8")
    assert "http_requests_total" in metrics_output
    assert 'method="GET"' in metrics_output
    assert 'endpoint="/api/v1/customers"' in metrics_output


def test_domain_metrics_counters_and_gauges() -> None:
    """Verify domain counter and gauge mutations generate valid Prometheus metrics output."""
    WHATSAPP_MESSAGES_INGESTED_TOTAL.labels(channel="WHATSAPP", status="STORED").inc()
    AI_EXTRACTION_ATTEMPTS_TOTAL.labels(status="PROVISIONAL").inc()
    QUOTATIONS_GENERATED_TOTAL.labels(vat_regime="NETTO").inc()
    DB_POOL_CONNECTIONS_ACTIVE.set(5)

    metrics_output = get_prometheus_metrics().decode("utf-8")
    assert "whatsapp_messages_ingested_total" in metrics_output
    assert "ai_extraction_attempts_total" in metrics_output
    assert "quotations_generated_total" in metrics_output
    assert "db_pool_connections_active" in metrics_output
