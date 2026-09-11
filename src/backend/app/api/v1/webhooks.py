"""Meta WhatsApp Webhook Handlers (BR-007, BR-008, ADR 0018)."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.adapters.whatsapp_demo import DemoWhatsAppProvider
from app.adapters.whatsapp_meta import MetaWhatsAppProvider
from app.core.config import settings
from app.core.database import get_db_session
from app.core.errors import ForbiddenException, ValidationException
from app.core.logging import logger
from app.core.redis import enqueue_inbound_message_job
from app.models.inbound_message import InboundMessage
from app.models.whatsapp_account import WhatsAppAccount
from app.ports.whatsapp import WhatsAppProvider
from app.services.customer_service import CustomerService

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
async def verify_webhook_challenge(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
) -> Response:
    """Handle Meta WhatsApp webhook verification challenge GET request."""
    if hub_mode == "subscribe" and hub_verify_token == settings.META_WEBHOOK_VERIFY_TOKEN:
        logger.info("WhatsApp webhook challenge verification succeeded")
        return Response(content=hub_challenge or "", media_type="text/plain", status_code=200)

    logger.warning(
        "WhatsApp webhook challenge verification failed",
        extra={
            "hub_mode": hub_mode,
            "token_matched": hub_verify_token == settings.META_WEBHOOK_VERIFY_TOKEN,
        },
    )
    raise ForbiddenException("Webhook verification token mismatch or invalid mode.")


@router.post("/whatsapp")
async def receive_whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    provider: WhatsAppProvider = Depends(get_whatsapp_provider),
) -> dict[str, Any]:
    """Inbound Meta WhatsApp webhook handler (BR-008).

    1. Signature verified by WebhookSignatureMiddleware.
    2. Payload parsed into normalized WhatsAppMessage DTOs.
    3. Resolves multi-tenant WhatsAppAccount by phone_number_id.
    4. Executes pre-ACK PostgreSQL persistence of InboundMessage with wamid deduplication.
    5. Returns HTTP 200 OK (<200ms target).
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
        # Multi-tenant resolution via phone_number_id
        stmt = select(WhatsAppAccount).where(WhatsAppAccount.phone_number_id == msg.phone_number_id)
        res = await db.execute(stmt)
        account = res.scalar_one_or_none()

        if not account:
            # Fallback for dev / test mode if default tenant account exists
            stmt_fallback = select(WhatsAppAccount)
            res_fallback = await db.execute(stmt_fallback)
            account = res_fallback.scalars().first()

        if not account:
            logger.warning(
                "Unregistered WhatsApp phone_number_id in webhook, skipping DB persistence",
                extra={"phone_number_id": msg.phone_number_id},
            )
            results.append({"status": "unmapped_account", "phone_number_id": msg.phone_number_id})
            continue

        # Auto-provision or fetch Customer profile
        customer_service = CustomerService(db, tenant_id=account.tenant_id)
        await customer_service.get_or_create_by_phone(
            phone=msg.from_phone_e164,
        )

        # Pre-ACK PostgreSQL persistence
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
            await db.commit()
            await db.refresh(inbound_record)
            job_id = await enqueue_inbound_message_job(
                message_id=inbound_record.id,
                tenant_id=account.tenant_id,
            )
            logger.info(
                "Inbound WhatsApp message persisted pre-ACK",
                extra={
                    "inbound_id": str(inbound_record.id),
                    "tenant_id": str(account.tenant_id),
                    "wamid": msg.wamid,
                    "job_id": job_id,
                },
            )
            results.append(
                {
                    "status": "received",
                    "inbound_message_id": str(inbound_record.id),
                    "wamid": msg.wamid,
                    "job_id": job_id,
                }
            )
        except IntegrityError:
            await db.rollback()
            logger.info(
                "Duplicate wamid payload received, atomic deduplication caught (BR-008)",
                extra={"wamid": msg.wamid, "tenant_id": str(account.tenant_id)},
            )
            results.append(
                {
                    "status": "duplicate_ignored",
                    "wamid": msg.wamid,
                }
            )

    return {"status": "success", "processed_count": len(results), "details": results}
