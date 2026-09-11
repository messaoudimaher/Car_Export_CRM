"""Unit tests for ARQ Inbox Worker and Tenant Security Context Validation (SEC-011)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import DeveloperSecurityException
from app.core.redis import enqueue_inbound_message_job
from app.models.inbound_message import InboundMessage
from app.workers.inbox_worker import dead_letter_job_handler, process_inbound_message


@pytest.mark.asyncio
async def test_process_inbound_message_success() -> None:
    """Verify worker processes message successfully and updates processed_at timestamp."""
    msg_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    inbound_msg = InboundMessage(
        id=msg_id,
        tenant_id=tenant_id,
        provider_message_id="wamid.test_12345",
        sender_phone_e164="+21698123456",
        content="Test content",
    )

    mock_session = AsyncMock()
    exec_mock = MagicMock()
    exec_mock.scalar_one_or_none.return_value = inbound_msg
    mock_session.execute.return_value = exec_mock

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session

    with patch("app.workers.inbox_worker.async_session_factory", mock_factory):
        result = await process_inbound_message(
            ctx={},
            message_id=str(msg_id),
            tenant_id=str(tenant_id),
        )

    assert result is True
    assert inbound_msg.processed_at is not None
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_inbound_message_tenant_mismatch_raises_security_exception() -> None:
    """Verify tenant_id mismatch raises DeveloperSecurityException and aborts (SEC-011)."""
    msg_id = uuid.uuid4()
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    inbound_msg = InboundMessage(
        id=msg_id,
        tenant_id=tenant_a_id,
        provider_message_id="wamid.test_12345",
        sender_phone_e164="+21698123456",
        content="Forged tenant test content",
    )

    mock_session = AsyncMock()
    exec_mock = MagicMock()
    exec_mock.scalar_one_or_none.return_value = inbound_msg
    mock_session.execute.return_value = exec_mock

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session

    with patch("app.workers.inbox_worker.async_session_factory", mock_factory):
        with pytest.raises(DeveloperSecurityException, match="Tenant context mismatch"):
            await process_inbound_message(
                ctx={},
                message_id=str(msg_id),
                tenant_id=str(tenant_b_id),
            )


@pytest.mark.asyncio
async def test_process_inbound_message_already_processed_skips() -> None:
    """Verify worker skips re-processing if processed_at is already set."""
    msg_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    already_processed_time = datetime.now(UTC)

    inbound_msg = InboundMessage(
        id=msg_id,
        tenant_id=tenant_id,
        provider_message_id="wamid.test_12345",
        sender_phone_e164="+21698123456",
        content="Already processed content",
        processed_at=already_processed_time,
    )

    mock_session = AsyncMock()
    exec_mock = MagicMock()
    exec_mock.scalar_one_or_none.return_value = inbound_msg
    mock_session.execute.return_value = exec_mock

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session

    with patch("app.workers.inbox_worker.async_session_factory", mock_factory):
        result = await process_inbound_message(
            ctx={},
            message_id=str(msg_id),
            tenant_id=str(tenant_id),
        )

    assert result is True
    assert inbound_msg.processed_at == already_processed_time
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_dead_letter_job_handler_logs_poison_payload() -> None:
    """Verify dead_letter_job_handler executes cleanly when capturing poison payloads."""
    exc = RuntimeError("Poison payload parsing error")
    await dead_letter_job_handler(ctx={}, job_id="job_dl_123", exc=exc)


@pytest.mark.asyncio
async def test_enqueue_inbound_message_job_fallback() -> None:
    """Verify enqueue_inbound_message_job handles Redis connection failure gracefully."""
    with patch("app.core.redis.get_redis_pool", side_effect=ConnectionError("Redis offline")):
        job_id = await enqueue_inbound_message_job(
            message_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
        )

    assert job_id is None
