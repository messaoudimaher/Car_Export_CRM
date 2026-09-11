"""Unit tests for Structured JSON Logging & Correlation Context."""

import json
import logging

from app.core.logging import JSONLogFormatter, correlation_id_ctx, tenant_id_ctx


def test_json_formatter_outputs_valid_json() -> None:
    """Verify JSONLogFormatter formats log record into valid JSON string."""
    formatter = JSONLogFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Sample log message",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["logger"] == "test_logger"
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "Sample log message"
    assert "timestamp" in parsed


def test_logging_injects_correlation_and_tenant_context() -> None:
    """Verify active contextvars are automatically injected into log dictionary."""
    formatter = JSONLogFormatter()
    token_corr = correlation_id_ctx.set("corr-12345")
    token_tenant = tenant_id_ctx.set("tenant-67890")

    try:
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Context trace test",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert parsed["correlation_id"] == "corr-12345"
        assert parsed["tenant_id"] == "tenant-67890"
    finally:
        correlation_id_ctx.reset(token_corr)
        tenant_id_ctx.reset(token_tenant)


def test_logging_redacts_sensitive_keys() -> None:
    """Verify sensitive fields like password or token are redacted."""
    formatter = JSONLogFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Auth attempt",
        args=(),
        exc_info=None,
    )
    setattr(record, "password", "secret_pass_123")  # noqa: B010, S105
    setattr(record, "jwt_secret", "secret_jwt_456")  # noqa: B010, S105

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["password"] == "[REDACTED]"  # noqa: S105
    assert parsed["jwt_secret"] == "[REDACTED]"  # noqa: S105
