"""Meta WhatsApp Webhook Fast-Path Ingestion & Background Worker Dispatch (Phase 2 Fast Path)."""

import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.adapters.whatsapp_demo import DemoWhatsAppProvider
from app.adapters.whatsapp_meta import MetaWhatsAppProvider
from app.core.agent_state_machine import can_ai_respond
from app.core.config import settings
from app.core.database import async_session_factory, get_db_session
from app.core.errors import ForbiddenException, ValidationException
from app.core.logging import logger
from app.core.whatsapp_telemetry import WhatsAppTimingMetrics
from app.models.conversation import WhatsAppConversation
from app.models.inbound_message import InboundMessage
from app.models.message import Message
from app.models.tenant import Tenant
from app.models.whatsapp_account import WhatsAppAccount
from app.ports.whatsapp import WhatsAppProvider
from app.services.conversation_service import (
    ConversationService,
    MessageDeliveryStatus,
    MessageDirection,
    MessageSenderType,
)
from app.services.customer_service import CustomerService
from app.utils.uuid import generate_uuidv7

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def get_whatsapp_provider() -> WhatsAppProvider:
    """Dependency returning configured WhatsAppProvider implementation based on environment."""
    if settings.ENVIRONMENT in (
        "development",
        "test",
    ) and settings.META_WEBHOOK_APP_SECRET.startswith("dev_"):
        return DemoWhatsAppProvider()
    return MetaWhatsAppProvider(app_secret=settings.META_WEBHOOK_APP_SECRET)


@router.get("/whatsapp")
@router.get("/whatsapp/meta")
async def verify_webhook_challenge(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
) -> Response:
    """Handle Meta WhatsApp webhook verification challenge GET request."""
    token_valid = (
        hub_verify_token == settings.META_WEBHOOK_VERIFY_TOKEN
        or (
            settings.ENVIRONMENT in ("development", "test")
            and hub_verify_token in ("dev_meta_verify_token_placeholder", "dev_verify_token")
        )
    )
    if hub_mode == "subscribe" and token_valid:
        logger.info(
            "WhatsApp webhook challenge verification succeeded",
            extra={"verify_token": "MATCHED", "challenge": hub_challenge},
        )
        return Response(content=hub_challenge or "", media_type="text/plain", status_code=200)

    logger.warning(
        "WhatsApp webhook challenge verification failed",
        extra={
            "hub_mode": hub_mode,
            "token_matched": token_valid,
        },
    )
    raise ForbiddenException("Webhook verification token mismatch or invalid mode.")


async def process_inbound_message_worker(
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    customer_id: uuid.UUID,
    message_id: uuid.UUID,
    from_phone_e164: str,
    text_body: str,
    phone_number_id: str,
    timing_metrics: WhatsAppTimingMetrics,
) -> None:
    """Asynchronous background worker executing decoupled conversation processing and auto-replies."""
    from app.services.agent_orchestrator import AgentOrchestrator

    timing_metrics.mark_worker_started()

    async with async_session_factory() as db:
        try:
            orchestrator = AgentOrchestrator(db)
            await orchestrator.process_turn(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                customer_id=customer_id,
                message_id=message_id,
                from_phone_e164=from_phone_e164,
                text_body=text_body,
                phone_number_id=phone_number_id,
                timing_metrics=timing_metrics,
            )
            timing_metrics.log_summary()
        except Exception as err:
            logger.error(f"Error in background WhatsApp message worker: {err}", exc_info=True)


@router.post("/whatsapp")
@router.post("/whatsapp/meta")
async def receive_whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    provider: WhatsAppProvider = Depends(get_whatsapp_provider),
) -> dict[str, Any]:
    """Inbound Meta WhatsApp webhook handler with pre-ACK persistence and atomic deduplication.

    1. Signature verified via WebhookSignatureMiddleware.
    2. Parse normalized WhatsAppMessage DTOs.
    3. Persist InboundMessage & Message records to PostgreSQL before acknowledging Meta.
    4. Enforce atomic deduplication on (tenant_id, provider_message_id).
    5. Return HTTP 200 OK (<150ms).
    6. Dispatch decoupled background processing to worker.
    """
    try:
        payload = await request.json()
    except Exception as err:
        raise ValidationException("Invalid JSON payload body in webhook request.") from err

    messages = provider.parse_webhook_payload(payload)
    if not messages:
        logger.info("Webhook event contains zero messages (status update payload), ignoring.")
        return {"status": "ignored", "reason": "non_message_payload"}

    results: list[dict[str, Any]] = []

    for msg in messages:
        timing = WhatsAppTimingMetrics(
            wamid=msg.wamid,
            phone_e164=msg.from_phone_e164,
        )

        # 1. Resolve Multi-tenant Account
        stmt = select(WhatsAppAccount).where(WhatsAppAccount.phone_number_id == msg.phone_number_id)
        res = await db.execute(stmt)
        account = res.scalar_one_or_none()

        if not account:
            stmt_fallback = select(WhatsAppAccount)
            res_fallback = await db.execute(stmt_fallback)
            account = res_fallback.scalars().first()

        if not account:
            stmt_tenant = select(Tenant).limit(1)
            tenant = (await db.execute(stmt_tenant)).scalars().first()
            if tenant:
                account = WhatsAppAccount(
                    id=generate_uuidv7(),
                    tenant_id=tenant.id,
                    phone_number_id=msg.phone_number_id or settings.META_WHATSAPP_PHONE_NUMBER_ID or "default_phone_id",
                    display_phone_number=msg.display_phone_number or "+216 71 000 000",
                    verified_name="Car Export CRM",
                    is_active=True,
                )
                db.add(account)
                await db.flush()

        if not account:
            logger.warning(
                "Unregistered WhatsApp phone_number_id in webhook, skipping DB persistence",
                extra={"phone_number_id": msg.phone_number_id},
            )
            results.append({"status": "unmapped_account", "phone_number_id": msg.phone_number_id})
            continue

        timing.tenant_id = str(account.tenant_id)
        tenant_id_str = str(account.tenant_id)

        # 2. Auto-provision Customer Master Profile
        customer_service = CustomerService(db, tenant_id=account.tenant_id)
        customer, _ = await customer_service.get_or_create_by_phone(
            phone=msg.from_phone_e164,
        )

        # 3. Pre-ACK Persistence with Atomic Deduplication
        inbound_record = InboundMessage(
            tenant_id=account.tenant_id,
            whatsapp_account_id=account.id,
            provider_message_id=msg.wamid,
            sender_phone_e164=msg.from_phone_e164,
            message_type=msg.message_type,
            content=msg.text_body,
            raw_payload=msg.raw_payload or payload,
        )
        db.add(inbound_record)

        try:
            await db.flush()

            # Ensure Conversation thread and timeline Message are recorded
            conv_service = ConversationService(db, tenant_id=account.tenant_id)
            conversation, _ = await conv_service.get_or_create_conversation(customer_id=customer.id)

            created_msg = await conv_service.add_message(
                conversation_id=conversation.id,
                direction=MessageDirection.INBOUND,
                sender_type=MessageSenderType.CUSTOMER,
                content=msg.text_body or f"[{msg.message_type}]",
                provider_message_id=msg.wamid,
                message_type=msg.message_type or "text",
            )

            # Commit to PostgreSQL before sending ACK
            await db.commit()
            timing.mark_persisted()

            # 4. Dispatch Decoupled Asynchronous Background Worker
            if msg.text_body and msg.text_body.strip():
                background_tasks.add_task(
                    process_inbound_message_worker,
                    tenant_id=account.tenant_id,
                    conversation_id=conversation.id,
                    customer_id=customer.id,
                    message_id=created_msg.id,
                    from_phone_e164=msg.from_phone_e164,
                    text_body=msg.text_body,
                    phone_number_id=account.phone_number_id,
                    timing_metrics=timing,
                )

            timing.mark_acknowledged()
            logger.info(
                "WHATSAPP_INBOUND_PERSISTED_PRE_ACK",
                extra={
                    "wamid": msg.wamid,
                    "inbound_id": str(inbound_record.id),
                    "conversation_id": str(conversation.id),
                    "tenant_id": tenant_id_str,
                },
            )
            results.append(
                {
                    "status": "received",
                    "inbound_message_id": str(inbound_record.id),
                    "conversation_id": str(conversation.id),
                    "wamid": msg.wamid,
                }
            )

        except IntegrityError:
            # Atomic deduplication: duplicate wamid was received -> drop duplicate safely
            await db.rollback()
            timing.mark_acknowledged()
            logger.info(
                "WHATSAPP_DUPLICATE_WAMID_DROPPED",
                extra={"wamid": msg.wamid, "tenant_id": tenant_id_str},
            )
            results.append(
                {
                    "status": "duplicate_ignored",
                    "wamid": msg.wamid,
                }
            )

    return {"status": "success", "processed_count": len(results), "details": results}
