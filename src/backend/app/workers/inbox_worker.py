"""ARQ Background Worker Task Queue Handler (SEC-011, BR-008)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.future import select

from app.core.database import async_session_factory
from app.core.errors import DeveloperSecurityException
from app.core.logging import logger
from app.core.redis import get_redis_settings
from app.models.inbound_message import InboundMessage


async def process_inbound_message(
    ctx: dict[str, Any],
    message_id: str,
    tenant_id: str,
) -> bool:
    """Process inbound message asynchronously with tenant context validation (SEC-011).

    Args:
        ctx: ARQ worker execution context dictionary.
        message_id: InboundMessage UUID string.
        tenant_id: Expected Tenant UUID string context.

    Raises:
        DeveloperSecurityException: If message.tenant_id != tenant_id context (SEC-011).

    Returns:
        bool: True if message processed successfully or skipped as duplicate.
    """
    message_uuid = uuid.UUID(message_id)
    tenant_uuid = uuid.UUID(tenant_id)

    async with async_session_factory() as session:
        stmt = select(InboundMessage).where(InboundMessage.id == message_uuid)
        res = await session.execute(stmt)
        inbound_msg = res.scalar_one_or_none()

        if not inbound_msg:
            logger.warning(
                "Inbound message record not found in worker process",
                extra={"message_id": message_id, "tenant_id": tenant_id},
            )
            return False

        # SEC-011: Strict Tenant Context Security Boundary Guard
        if inbound_msg.tenant_id != tenant_uuid:
            logger.error(
                "SECURITY_WORKER_TENANT_MISMATCH: Worker task tenant_id mismatch detected",
                extra={
                    "message_id": message_id,
                    "expected_tenant_id": tenant_id,
                    "actual_tenant_id": str(inbound_msg.tenant_id),
                },
            )
            raise DeveloperSecurityException(
                "Tenant context mismatch in background worker job execution."
            )

        if inbound_msg.processed_at is not None:
            logger.info(
                "Inbound message already processed, skipping duplicate execution",
                extra={"message_id": message_id, "tenant_id": tenant_id},
            )
            return True

        # Process message asynchronous AI parameters / operational fields
        inbound_msg.processed_at = datetime.now(UTC)
        await session.commit()

        from app.core.ws_manager import ws_manager

        await ws_manager.broadcast_to_tenant(
            tenant_id=tenant_uuid,
            event_type="INBOX_MESSAGE_RECEIVED",
            data={
                "id": str(inbound_msg.id),
                "tenant_id": str(inbound_msg.tenant_id),
                "provider_message_id": inbound_msg.provider_message_id,
                "sender_phone_e164": inbound_msg.sender_phone_e164,
                "message_type": inbound_msg.message_type,
                "content": inbound_msg.content,
            },
        )

        logger.info(
            "Successfully processed inbound WhatsApp message background job",
            extra={
                "message_id": message_id,
                "tenant_id": tenant_id,
                "processed_at": inbound_msg.processed_at.isoformat(),
            },
        )
        return True


async def dead_letter_job_handler(
    ctx: dict[str, Any],
    job_id: str,
    exc: Exception,
) -> None:
    """Handle poison payloads reaching max retries by logging to dead-letter queue (SEC-011)."""
    logger.error(
        "SECURITY_DEAD_LETTER_JOB: Job reached max retries, moved to dead letter storage",
        extra={"job_id": job_id, "error_type": exc.__class__.__name__, "error": str(exc)},
        exc_info=exc,
    )


class WorkerSettings:
    """ARQ Worker Configuration Settings."""

    functions = [process_inbound_message]
    on_job_failure = dead_letter_job_handler
    max_retries = 3
    redis_settings = get_redis_settings()
