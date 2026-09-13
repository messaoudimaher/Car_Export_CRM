"""Immutable Security Audit Event Logging Engine (BR-016, INV-009, SECURITY.md Section 15).

This service provides sanitized, append-only security audit event persistence with automatic
data scrubbing for credentials, tokens, secrets, and sensitive authentication headers.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_correlation_id, logger
from app.models.audit_event import AuditEvent

REDACTED_TEXT = "[REDACTED_SENSITIVE_DATA]"

SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "whatsapp_app_secret",
    "authorization",
    "cookie",
    "credit_card",
    "cvv",
    "bearer",
    "jwt",
    "private_key",
}


def scrub_sensitive_data(data: Any) -> Any:
    """Recursively scrub sensitive credential and authentication keys from payloads (INV-009).

    Args:
        data: Arbitrary dictionary, list, or scalar payload.

    Returns:
        Any: Sanitized copy of data payload with sensitive keys redacted.
    """
    if data is None:
        return None

    if isinstance(data, dict):
        sanitized: dict[str, Any] = {}
        for key, val in data.items():
            key_str = str(key).lower()
            if any(sensitive_key in key_str for sensitive_key in SENSITIVE_KEYS):
                sanitized[key] = REDACTED_TEXT
            else:
                sanitized[key] = scrub_sensitive_data(val)
        return sanitized

    if isinstance(data, list):
        return [scrub_sensitive_data(item) for item in data]

    if isinstance(data, str) and data.lower().startswith("bearer "):
        return REDACTED_TEXT

    return data


class AuditService:
    """Service providing sanitized append-only audit event logging."""

    @classmethod
    async def record_audit_event(
        cls,
        session: AsyncSession,
        action: str,
        tenant_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        resource_type: str = "System",
        resource_id: str | None = None,
        payload_before: dict[str, Any] | None = None,
        payload_after: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        correlation_id: str | None = None,
    ) -> AuditEvent:
        """Record a sanitized append-only audit event to persistent storage (BR-016, INV-009).

        Args:
            session: AsyncSession instance.
            action: Categorized action identifier string (e.g. QUOTE_APPROVED).
            tenant_id: Optional parent tenant organization UUID.
            user_id: Optional acting user identity UUID.
            resource_type: Target entity class or domain (e.g. Quotation, Document).
            resource_id: Target entity ID string.
            payload_before: Optional pre-action state dictionary.
            payload_after: Optional post-action state dictionary.
            ip_address: Optional client IPv4/IPv6 address.
            user_agent: Optional client HTTP User-Agent string.
            correlation_id: Optional HTTP correlation trace ID.

        Returns:
            AuditEvent: Persisted AuditEvent model instance.
        """
        sanitized_before = scrub_sensitive_data(payload_before)
        sanitized_after = scrub_sensitive_data(payload_after)
        corr_id = correlation_id or get_correlation_id()

        event = AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            payload_before=sanitized_before,
            payload_after=sanitized_after,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=corr_id,
        )

        session.add(event)

        logger.info(
            "security_audit_event_recorded action=%s tenant_id=%s user_id=%s resource_type=%s resource_id=%s correlation_id=%s",
            action,
            str(tenant_id) if tenant_id else "system",
            str(user_id) if user_id else "system",
            resource_type,
            str(resource_id),
            corr_id or "none",
        )

        return event
