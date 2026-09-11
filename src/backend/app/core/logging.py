"""Structured JSON Logging Infrastructure with Correlation ID Propagation."""

import contextvars
import json
import logging
import sys
from typing import Any

# Context variables for correlation and request tracing
correlation_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
tenant_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tenant_id", default=None
)
user_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("user_id", default=None)


class JSONLogFormatter(logging.Formatter):
    """Custom JSON Formatter injecting correlation tracing and sanitizing sensitive keys."""

    SENSITIVE_KEYS = {
        "password",
        "token",
        "secret",
        "access_token",
        "jwt_secret",
        "api_key",
        "authorization",
        "meta_webhook_app_secret",
    }

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Inject context variables if available
        corr_id = correlation_id_ctx.get()
        if corr_id:
            log_data["correlation_id"] = corr_id

        tenant_id = tenant_id_ctx.get()
        if tenant_id:
            log_data["tenant_id"] = tenant_id

        user_id = user_id_ctx.get()
        if user_id:
            log_data["user_id"] = user_id

        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Include extra variables passed to logger calls
        for key, value in record.__dict__.items():
            if key not in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            }:
                # Sanitize sensitive fields
                if any(sensitive in key.lower() for sensitive in self.SENSITIVE_KEYS):
                    log_data[key] = "[REDACTED]"
                else:
                    log_data[key] = value

        return json.dumps(log_data)


def configure_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure root logger to output structured JSON to stdout."""
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Remove pre-existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(JSONLogFormatter())
    root_logger.addHandler(stream_handler)

    return logging.getLogger("app")


logger = configure_logging()
