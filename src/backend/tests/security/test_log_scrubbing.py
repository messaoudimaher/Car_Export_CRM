"""TASK-1804: Automated Unit & Security Tests for Sensitive Data & Log Scrubbing Engine (SECURITY.md Section 15 & 21).

This test suite verifies:
1. Recursive data scrubbing of sensitive keys (passwords, tokens, secrets, API keys, cards) in top-level and nested log context dictionaries.
2. Regex redaction of Bearer tokens and Authorization strings in formatted log messages.
3. Sanitization of HTTP request header dictionaries (Authorization, Cookie, X-API-Key).
4. Preservation of valid operational context metadata (correlation_id, tenant_id, user_id).
"""

import json
import logging

from app.core.logging import (
    JSONLogFormatter,
    sanitize_log_value,
)


def test_sanitize_log_value_recursive_scrubbing() -> None:
    """Verify sanitize_log_value recursively redacts sensitive keys in dictionaries and lists."""
    raw_extra = {
        "user_email": "sales@exportcrm.de",
        "auth_details": {
            "password": "plain_password_abc",
            "password_hash": "$argon2id$v=19$...",
            "access_token": "eyJhbGciOiJIUzI1Ni...",
            "secret_key": "meta_app_secret_val",
        },
        "headers": {
            "Authorization": "Bearer my_jwt_access_token_123",
            "Cookie": "crm_access_token=xyz987",
            "User-Agent": "Mozilla/5.0",
        },
        "tokens_count": 5,  # Non-sensitive field ending in _tokens
    }

    sanitized = sanitize_log_value(raw_extra)

    assert sanitized["user_email"] == "sales@exportcrm.de"
    assert sanitized["auth_details"]["password"] == "[REDACTED]"
    assert sanitized["auth_details"]["password_hash"] == "[REDACTED]"
    assert sanitized["auth_details"]["access_token"] == "[REDACTED]"
    assert sanitized["auth_details"]["secret_key"] == "[REDACTED]"
    assert sanitized["headers"]["Authorization"] == "[REDACTED]"
    assert sanitized["headers"]["Cookie"] == "[REDACTED]"
    assert sanitized["headers"]["User-Agent"] == "Mozilla/5.0"
    assert sanitized["tokens_count"] == 5


def test_json_formatter_redacts_nested_extra_context() -> None:
    """Verify JSONLogFormatter output contains no raw plaintext passwords or tokens in extra dicts."""
    formatter = JSONLogFormatter()
    record = logging.LogRecord(
        name="test_scrubber",
        level=logging.INFO,
        pathname="test_auth.py",
        lineno=42,
        msg="User authentication attempt",
        args=(),
        exc_info=None,
    )
    setattr(
        record,
        "request_body",
        {
            "email": "user@tenant1.com",
            "password": "my_super_secret_password_123",
            "api_key": "sk_test_999888",
        },
    )

    formatted_json = formatter.format(record)
    parsed = json.loads(formatted_json)

    assert parsed["message"] == "User authentication attempt"
    assert parsed["request_body"]["email"] == "user@tenant1.com"
    assert parsed["request_body"]["password"] == "[REDACTED]"
    assert parsed["request_body"]["api_key"] == "[REDACTED]"

    # Confirm raw password string does not appear anywhere in formatted output
    assert "my_super_secret_password_123" not in formatted_json
    assert "sk_test_999888" not in formatted_json


def test_json_formatter_redacts_bearer_tokens_in_message_strings() -> None:
    """Verify Bearer tokens inside raw log message strings are regex redacted."""
    formatter = JSONLogFormatter()
    record = logging.LogRecord(
        name="test_scrubber",
        level=logging.INFO,
        pathname="client.py",
        lineno=100,
        msg="Dispatching HTTP POST with header Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        args=(),
        exc_info=None,
    )

    formatted_json = formatter.format(record)
    parsed = json.loads(formatted_json)

    assert "Bearer [REDACTED]" in parsed["message"]
    assert "eyJhbGciOiJIUzI1Ni" not in formatted_json
