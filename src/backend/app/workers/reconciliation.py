"""Database Reconciliation Job for Unqueued PostgreSQL Inbound Messages (TASK-0605)."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import async_session_factory
from app.core.logging import logger
from app.core.redis import enqueue_inbound_message_job
from app.models.inbound_message import InboundMessage


async def reconcile_unqueued_messages(
    session: AsyncSession,
    max_age_minutes: int = 5,
    batch_size: int = 100,
) -> int:
    """Query unprocessed InboundMessage records and re-enqueue them into ARQ Redis.

    Args:
        session: Active AsyncSession database session.
        max_age_minutes: Threshold age cutoff in minutes for considering a message unqueued.
        batch_size: Maximum number of records to process in a single execution.

    Returns:
        int: Total number of unqueued messages successfully re-enqueued.
    """
    cutoff_time = datetime.now(UTC) - timedelta(minutes=max_age_minutes)

    stmt = (
        select(InboundMessage)
        .where(
            InboundMessage.processed_at.is_(None),
            InboundMessage.created_at <= cutoff_time,
        )
        .order_by(InboundMessage.created_at.asc())
        .limit(batch_size)
    )

    result = await session.execute(stmt)
    unqueued_messages = result.scalars().all()

    if not unqueued_messages:
        logger.info("Reconciliation check completed: zero unqueued messages found.")
        return 0

    re_enqueued_count = 0
    for msg in unqueued_messages:
        job_id = await enqueue_inbound_message_job(
            message_id=msg.id,
            tenant_id=msg.tenant_id,
        )
        if job_id is not None:
            re_enqueued_count += 1
            logger.info(
                "Re-enqueued orphaned inbound message job via DB reconciliation",
                extra={
                    "message_id": str(msg.id),
                    "tenant_id": str(msg.tenant_id),
                    "job_id": job_id,
                },
            )

    logger.info(
        "DB Reconciliation job completed execution",
        extra={
            "found_count": len(unqueued_messages),
            "re_enqueued_count": re_enqueued_count,
        },
    )
    return re_enqueued_count


async def run_reconciliation_cron(ctx: dict[str, Any]) -> int:
    """ARQ Cron Task Entrypoint for periodic DB message reconciliation."""
    async with async_session_factory() as session:
        return await reconcile_unqueued_messages(session)
