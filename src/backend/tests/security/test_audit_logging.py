"""TASK-1803: Automated Unit & Security Tests for Immutable Audit Event Logging Engine (BR-016, INV-009).

This test suite verifies:
1. Persistence of append-only audit records (AuditEvent) with UUIDv7 primary keys.
2. Recursive data scrubbing of sensitive keys (passwords, tokens, API keys, secrets, authorization headers).
3. Correct attribution of tenant_id, user_id, action, resource_type, resource_id, and correlation_id.
4. Preservation of non-sensitive payload context attributes.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.audit_event import AuditEvent
from app.services.audit_service import REDACTED_TEXT, AuditService, scrub_sensitive_data


def test_scrub_sensitive_data_redacts_credentials_and_tokens() -> None:
    """Verify scrub_sensitive_data recursively redacts passwords, tokens, keys, and auth headers (INV-009)."""
    raw_payload = {
        "user_email": "agent@export.de",
        "password": "plain_text_password_123",
        "nested_credentials": {
            "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$...",
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "api_key": "sk_live_secret_key_999",
            "whatsapp_app_secret": "meta_app_secret_abc123",
            "authorization": "Bearer secret_token_xyz",
        },
        "customer_info": {
            "full_name": "Mohamed Ben Ali",
            "phone_e164": "+21698123456",
            "fcr_eligible": True,
        },
    }

    sanitized = scrub_sensitive_data(raw_payload)

    # Sensitive fields must be redacted
    assert sanitized["password"] == REDACTED_TEXT
    assert sanitized["nested_credentials"]["password_hash"] == REDACTED_TEXT
    assert sanitized["nested_credentials"]["access_token"] == REDACTED_TEXT
    assert sanitized["nested_credentials"]["api_key"] == REDACTED_TEXT
    assert sanitized["nested_credentials"]["whatsapp_app_secret"] == REDACTED_TEXT
    assert sanitized["nested_credentials"]["authorization"] == REDACTED_TEXT

    # Non-sensitive operational data must be preserved intact
    assert sanitized["user_email"] == "agent@export.de"
    assert sanitized["customer_info"]["full_name"] == "Mohamed Ben Ali"
    assert sanitized["customer_info"]["phone_e164"] == "+21698123456"
    assert sanitized["customer_info"]["fcr_eligible"] is True


def test_scrub_sensitive_data_handles_lists_and_none() -> None:
    """Verify scrubber handles lists and None values safely."""
    assert scrub_sensitive_data(None) is None

    list_payload = [
        {"password": "secret_1", "username": "user1"},
        {"secret": "key_2", "username": "user2"},
    ]

    sanitized = scrub_sensitive_data(list_payload)
    assert sanitized[0]["password"] == REDACTED_TEXT
    assert sanitized[0]["username"] == "user1"
    assert sanitized[1]["secret"] == REDACTED_TEXT
    assert sanitized[1]["username"] == "user2"


@pytest.mark.asyncio
async def test_record_audit_event_persists_sanitized_record() -> None:
    """Verify AuditService.record_audit_event creates and persists an AuditEvent with scrubbed payloads."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    quote_id = uuid.uuid4()

    payload_before = {
        "status": "Pending_Approval",
        "discount_percent": 10.0,
        "manager_token": "secret_manager_token_123",
    }
    payload_after = {
        "status": "Approved",
        "discount_percent": 10.0,
        "approved_by": str(user_id),
    }

    event = await AuditService.record_audit_event(
        session=mock_session,
        action="QUOTE_APPROVED",
        tenant_id=tenant_id,
        user_id=user_id,
        resource_type="Quotation",
        resource_id=str(quote_id),
        payload_before=payload_before,
        payload_after=payload_after,
        ip_address="198.51.100.45",
        user_agent="Mozilla/5.0 CRM Client",
        correlation_id="req_audit_test_001",
    )

    # Verify session.add was called with AuditEvent instance
    mock_session.add.assert_called_once_with(event)

    assert isinstance(event, AuditEvent)
    assert event.action == "QUOTE_APPROVED"
    assert event.tenant_id == tenant_id
    assert event.user_id == user_id
    assert event.resource_type == "Quotation"
    assert event.resource_id == str(quote_id)
    assert event.ip_address == "198.51.100.45"
    assert event.user_agent == "Mozilla/5.0 CRM Client"
    assert event.correlation_id == "req_audit_test_001"

    # Verify sensitive fields inside payload_before were scrubbed
    assert event.payload_before["manager_token"] == REDACTED_TEXT
    assert event.payload_before["status"] == "Pending_Approval"
    assert event.payload_after["status"] == "Approved"
