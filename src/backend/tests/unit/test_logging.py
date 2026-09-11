"""Unit tests for Structured JSON Logging & Correlation Context."""

import json
import logging

from app.core.logging import (
    JSONLogFormatter,
    correlation_id_ctx,
    get_correlation_id,
    get_logger,
    get_tenant_id,
    get_user_id,
    set_correlation_id,
    set_tenant_id,
    set_user_id,
    tenant_id_ctx,
    user_id_ctx,
)


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
    token_corr = set_correlation_id("corr-12345")
    token_tenant = set_tenant_id("tenant-67890")
    token_user = set_user_id("user-11223")

    try:
        assert get_correlation_id() == "corr-12345"
        assert get_tenant_id() == "tenant-67890"
        assert get_user_id() == "user-11223"

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
        assert parsed["user_id"] == "user-11223"
    finally:
        correlation_id_ctx.reset(token_corr)
        tenant_id_ctx.reset(token_tenant)
        user_id_ctx.reset(token_user)


def test_logging_redacts_sensitive_keys() -> None:
    """Verify sensitive fields like password, tokens, and provider keys are redacted."""
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
    setattr(record, "llm_provider_api_key", "sk-123456789")  # noqa: B010, S105
    setattr(record, "s3_secret_access_key", "s3-secret-key")  # noqa: B010, S105

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["password"] == "[REDACTED]"  # noqa: S105
    assert parsed["jwt_secret"] == "[REDACTED]"  # noqa: S105
    assert parsed["llm_provider_api_key"] == "[REDACTED]"  # noqa: S105
    assert parsed["s3_secret_access_key"] == "[REDACTED]"  # noqa: S105


def test_get_logger_factory() -> None:
    """Verify get_logger returns a logging.Logger instance."""
    logger = get_logger("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"
