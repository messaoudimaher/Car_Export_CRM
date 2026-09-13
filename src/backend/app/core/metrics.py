"""Prometheus Metrics Exporter Module (TASK-2001 / WS-20).

Exposes system, application, database, HTTP, and operational CRM metrics
in standard Prometheus text exposition format.
"""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Registry reference
registry: CollectorRegistry = REGISTRY

# 1. HTTP Metrics
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total count of HTTP requests handled by FastAPI application.",
    ["method", "endpoint", "status_code"],
    registry=registry,
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "Histogram of HTTP request latency in seconds.",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=registry,
)

# 2. Database & Connection Metrics
DB_POOL_CONNECTIONS_ACTIVE = Gauge(
    "db_pool_connections_active",
    "Current count of active PostgreSQL database connections in the async engine pool.",
    registry=registry,
)

DB_POOL_CONNECTIONS_OVERFLOW = Gauge(
    "db_pool_connections_overflow",
    "Current count of overflow connections in the database pool.",
    registry=registry,
)

# 3. Queue & Background Worker Metrics
ARQ_QUEUE_DEPTH = Gauge(
    "arq_queue_depth",
    "Current number of pending background jobs in the Redis ARQ queue.",
    ["queue_name"],
    registry=registry,
)

# 4. Domain & Business Process Metrics
WHATSAPP_MESSAGES_INGESTED_TOTAL = Counter(
    "whatsapp_messages_ingested_total",
    "Total count of inbound WhatsApp messages ingested into PostgreSQL.",
    ["channel", "status"],
    registry=registry,
)

AI_EXTRACTION_ATTEMPTS_TOTAL = Counter(
    "ai_extraction_attempts_total",
    "Total count of AI understanding extraction attempts.",
    ["status"],
    registry=registry,
)

QUOTATIONS_GENERATED_TOTAL = Counter(
    "quotations_generated_total",
    "Total count of FCR car export quotation PDFs generated.",
    ["vat_regime"],
    registry=registry,
)

SECURITY_AUDIT_EVENTS_TOTAL = Counter(
    "security_audit_events_total",
    "Total count of security audit events logged to the append-only ledger.",
    ["action"],
    registry=registry,
)


def get_prometheus_metrics() -> bytes:
    """Generate latest Prometheus metrics formatted string."""
    return generate_latest(registry)


def record_http_request(method: str, endpoint: str, status_code: int, duration_seconds: float) -> None:
    """Helper to record HTTP request metrics."""
    HTTP_REQUESTS_TOTAL.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        method=method,
        endpoint=endpoint,
    ).observe(duration_seconds)
