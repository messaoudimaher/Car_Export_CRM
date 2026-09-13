"""Scheduled Follow-Up Reminder Worker Job (WS-14, TASK-1402, SEC-007)."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.ws_manager import ws_manager
from app.models.followup import FollowUp, FollowUpStatus

logger = logging.getLogger(__name__)


async def scan_and_notify_due_followups(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """Scan database for due follow-up tasks and emit real-time WebSocket reminders (TASK-1402).

    Scans for tasks matching:
    - due_at <= NOW() (UTC)
    - status = 'Pending'
    - reminder_sent = False

    Returns:
        dict: Summary containing scanned_count and notifications_sent count.
    """
    now_utc = datetime.now(UTC)
    notifications_sent = 0

    async with async_session_factory() as session:
        stmt = (
            select(FollowUp)
            .where(
                FollowUp.due_at <= now_utc,
                FollowUp.status == FollowUpStatus.PENDING.value,
                FollowUp.reminder_sent.is_(False),
            )
            .order_by(FollowUp.due_at.asc())
            .limit(200)
        )

        result = await session.execute(stmt)
        due_tasks = list(result.scalars().all())

        if not due_tasks:
            logger.debug("FollowUp worker scan: 0 due tasks found.")
            return {"scanned_count": 0, "notifications_sent": 0}

        for task in due_tasks:
            task_tenant_id = (
                task.tenant_id
                if isinstance(task.tenant_id, uuid.UUID)
                else uuid.UUID(str(task.tenant_id))
            )

            # Emit real-time WebSocket notification to tenant workspace (TASK-0704, TASK-1402)
            await ws_manager.broadcast_to_tenant(
                tenant_id=task_tenant_id,
                event_type="FOLLOWUP_REMINDER_DUE",
                data={
                    "followup_id": str(task.id),
                    "tenant_id": str(task.tenant_id),
                    "lead_id": str(task.lead_id),
                    "assigned_user_id": str(task.assigned_user_id)
                    if task.assigned_user_id
                    else None,
                    "title": task.title,
                    "description": task.description,
                    "due_at": task.due_at.isoformat(),
                    "status": task.status,
                },
            )

            task.reminder_sent = True
            notifications_sent += 1

        await session.commit()

        logger.info(
            f"FollowUp worker scan: processed {len(due_tasks)} due tasks",
            extra={"scanned_count": len(due_tasks), "notifications_sent": notifications_sent},
        )

        return {
            "scanned_count": len(due_tasks),
            "notifications_sent": notifications_sent,
        }
