"""Unit tests for Database Message Reconciliation Runner (TASK-0605)."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.inbound_message import InboundMessage
from app.workers.reconciliation import reconcile_unqueued_messages, run_reconciliation_cron


@pytest.mark.asyncio
async def test_reconcile_unqueued_messages_finds_and_re_enqueues() -> None:
    """Verify reconciliation query identifies unqueued messages and re-enqueues them."""
    tenant_id = uuid.uuid4()
    msg = InboundMessage(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        provider_message_id="wamid.orphaned_12345",
        sender_phone_e164="+21698123456",
        content="Orphaned message",
        created_at=datetime.now(UTC) - timedelta(minutes=10),
        processed_at=None,
    )

    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [msg]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    with patch(
        "app.workers.reconciliation.enqueue_inbound_message_job",
        AsyncMock(return_value="job_re_999"),
    ):
        re_enqueued_count = await reconcile_unqueued_messages(mock_session, max_age_minutes=5)

    assert re_enqueued_count == 1
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconcile_unqueued_messages_zero_when_no_orphans() -> None:
    """Verify reconciliation returns 0 when no orphaned messages are found."""
    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    re_enqueued_count = await reconcile_unqueued_messages(mock_session, max_age_minutes=5)

    assert re_enqueued_count == 0


@pytest.mark.asyncio
async def test_run_reconciliation_cron_entrypoint() -> None:
    """Verify run_reconciliation_cron entrypoint executes database session lifecycle."""
    mock_session = AsyncMock()
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session

    with (
        patch("app.workers.reconciliation.async_session_factory", mock_factory),
        patch("app.workers.reconciliation.reconcile_unqueued_messages", AsyncMock(return_value=2)),
    ):
        result = await run_reconciliation_cron(ctx={})

    assert result == 2
