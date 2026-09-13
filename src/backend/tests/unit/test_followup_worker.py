"""Unit tests for FollowUp Worker Job scanning & WebSocket reminders (WS-14, TASK-1402)."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.followup import FollowUp, FollowUpStatus
from app.workers.followup_worker import scan_and_notify_due_followups


@pytest.mark.asyncio
async def test_scan_and_notify_due_followups_worker() -> None:
    """Verify worker job scans due tasks, emits WebSocket event, and updates reminder_sent flag."""
    tenant_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    user_id = uuid.uuid4()
    past_due = datetime.now(UTC) - timedelta(minutes=10)

    mock_task = FollowUp(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        lead_id=lead_id,
        assigned_user_id=user_id,
        title="Follow up on customer deposit invoice",
        due_at=past_due,
        status=FollowUpStatus.PENDING.value,
        reminder_sent=False,
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [mock_task]
    mock_session.execute.return_value = mock_result

    mock_factory = MagicMock(__aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock())
    ws_patch = patch("app.core.ws_manager.ws_manager.broadcast_to_tenant", new_callable=AsyncMock)

    with (
        patch("app.workers.followup_worker.async_session_factory", return_value=mock_factory),
        ws_patch as mock_bcast,
    ):
        result = await scan_and_notify_due_followups()

        assert result["scanned_count"] == 1
        assert result["notifications_sent"] == 1
        assert mock_task.reminder_sent is True
        mock_bcast.assert_called_once()
        mock_session.commit.assert_called_once()
