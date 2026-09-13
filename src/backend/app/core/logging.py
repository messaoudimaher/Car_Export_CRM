"""Structured JSON Logging Infrastructure with Correlation Context Tracing."""

import contextvars
import json
import logging
import re
import sys
from typing import Any

# Context variables for request tracing across async tasks
correlation_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
tenant_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tenant_id", default=None
)
user_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("user_id", default=None)


def get_correlation_id() -> str | None:
    """Return the active request correlation ID from context."""
    return correlation_id_ctx.get()


def set_correlation_id(correlation_id: str) -> contextvars.Token[str | None]:
    """Set the active request correlation ID in context."""
    return correlation_id_ctx.set(correlation_id)


def get_tenant_id() -> str | None:
    """Return the active tenant ID from context."""
    return tenant_id_ctx.get()


def set_tenant_id(tenant_id: str) -> contextvars.Token[str | None]:
    """Set the active tenant ID in context."""
    return tenant_id_ctx.set(tenant_id)


def get_user_id() -> str | None:
    """Return the active user ID from context."""
    return user_id_ctx.get()


def set_user_id(user_id: str) -> contextvars.Token[str | None]:
    """Set the active user ID in context."""
    return user_id_ctx.set(user_id)


BEARER_TOKEN_REGEX = re.compile(r"(Bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*", re.IGNORECASE)
REDACTED_TEXT = "[REDACTED]"

SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "pass",
    "pwd",
    "secret",
    "jwt_secret",
    "api_key",
    "x-api-key",
    "access_token",
    "refresh_token",
    "auth_token",
    "session_token",
    "authorization",
    "cookie",
    "set-cookie",
    "whatsapp_app_secret",
    "meta_app_secret",
    "meta_webhook_app_secret",
    "meta_webhook_verify_token",
    "s3_secret_access_key",
    "llm_provider_api_key",
    "embedding_provider_api_key",
    "credit_card",
    "card_number",
    "cvv",
}


def is_sensitive_key(key_name: str) -> bool:
    """Determine whether a dictionary key represents a sensitive credential field."""
    k = key_name.lower()
    if k in {"token", "jwt", "bearer"}:
        return True
    if any(sensitive in k for sensitive in SENSITIVE_KEYS):
        return True
    return False


def sanitize_log_value(value: Any) -> Any:
    """Recursively sanitize dictionary, list, and scalar values for structured logging."""
    if value is None:
        return None

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for k, v in value.items():
            if is_sensitive_key(str(k)):
                sanitized[k] = REDACTED_TEXT
            else:
                sanitized[k] = sanitize_log_value(v)
        return sanitized

    if isinstance(value, list):
        return [sanitize_log_value(item) for item in value]

    if isinstance(value, str):
        if BEARER_TOKEN_REGEX.search(value):
            return BEARER_TOKEN_REGEX.sub(r"\1" + REDACTED_TEXT, value)

    return value


class JSONLogFormatter(logging.Formatter):
    """Custom JSON Formatter injecting correlation tracing and sanitizing sensitive keys."""

    SENSITIVE_KEYS = SENSITIVE_KEYS

    def format(self, record: logging.LogRecord) -> str:
        msg_str = record.getMessage()
        if BEARER_TOKEN_REGEX.search(msg_str):
            msg_str = BEARER_TOKEN_REGEX.sub(r"\1" + REDACTED_TEXT, msg_str)

        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "module": record.module,
            "logger": record.name,
            "message": msg_str,
        }

        # Inject context variables if available
        corr_id = get_correlation_id()
        if corr_id:
            log_data["correlation_id"] = corr_id

        tenant_id = get_tenant_id()
        if tenant_id:
            log_data["tenant_id"] = tenant_id

        user_id = get_user_id()
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
                # Sanitize sensitive fields recursively
                if is_sensitive_key(key):
                    log_data[key] = REDACTED_TEXT
                else:
                    log_data[key] = sanitize_log_value(value)

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


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger instance for the given module name."""
    return logging.getLogger(name or "app")


logger = configure_logging()
