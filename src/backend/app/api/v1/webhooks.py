"""Meta WhatsApp Webhook Handlers (BR-007, BR-008, ADR 0018)."""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
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
@router.get("/whatsapp/meta")
async def verify_webhook_challenge(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
) -> Response:
    """Handle Meta WhatsApp webhook verification challenge GET request."""
    if hub_mode == "subscribe" and (
        hub_verify_token == settings.META_WEBHOOK_VERIFY_TOKEN
        or settings.ENVIRONMENT in ("development", "test")
    ):
        logger.info(
            "WhatsApp webhook challenge verification succeeded",
            extra={"verify_token": hub_verify_token, "challenge": hub_challenge},
        )
        return Response(content=hub_challenge or "", media_type="text/plain", status_code=200)

    logger.warning(
        "WhatsApp webhook challenge verification failed",
        extra={
            "hub_mode": hub_mode,
            "token_matched": hub_verify_token == settings.META_WEBHOOK_VERIFY_TOKEN,
        },
    )
    raise ForbiddenException("Webhook verification token mismatch or invalid mode.")


async def _process_ai_and_auto_reply(
    tenant_id: Any,
    conversation_id: Any,
    customer_id: Any,
    message_id: Any,
    from_phone_e164: str,
    text_body: str,
    phone_number_id: str,
) -> None:
    """Asynchronous background worker for Gemini AI extraction, auto-reply drafting, and dispatch with multi-turn memory."""
    import json
    import re
    from app.adapters.llm_gemini import GeminiAdapter
    from app.adapters.whatsapp_meta import MetaWhatsAppProvider
    from app.core.agent_policy import load_agent_policy
    from app.core.database import async_session_factory
    from app.core.ws_manager import ws_manager
    from app.models.ai_suggestion import AISuggestion, AISuggestionStatus
    from app.models.ai_understanding import AIUnderstanding, AIUnderstandingStatus
    from app.models.message import Message
    from app.ports.llm import LLMCompletionRequest
    from app.schemas.vehicle_request_extraction import (
        VehicleRequestExtraction,
        validate_vehicle_request,
    )
    from app.services.conversation_service import (
        ConversationService,
        MessageDeliveryStatus,
        MessageDirection,
        MessageSenderType,
    )

    async with async_session_factory() as db:
        try:
            # 1. Fetch entire conversation timeline for this thread in chronological order
            stmt_msgs = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
            )
            history_records = list((await db.execute(stmt_msgs)).scalars().all())

            chat_turns: list[dict[str, str]] = []
            turn_count = 0
            has_previous_outbound = False

            for h_msg in history_records:
                is_inbound = (
                    h_msg.direction == MessageDirection.INBOUND
                    or str(h_msg.direction).lower() == "inbound"
                    or h_msg.sender_type == MessageSenderType.CUSTOMER
                )
                if not is_inbound:
                    has_previous_outbound = True
                else:
                    turn_count += 1
                role = "user" if is_inbound else "model"
                if h_msg.content and h_msg.content.strip():
                    chat_turns.append({"role": role, "content": h_msg.content.strip()})

            is_first_turn = not has_previous_outbound and turn_count <= 1

            # 2. Retrieve previous vehicle understandings to accumulate search criteria across turns
            stmt_prev_und = (
                select(AIUnderstanding)
                .where(AIUnderstanding.conversation_id == conversation_id)
                .order_by(AIUnderstanding.created_at.desc())
                .limit(10)
            )
            prev_understandings = list((await db.execute(stmt_prev_und)).scalars().all())
            accumulated_criteria: dict[str, Any] = {}
            for u in reversed(prev_understandings):
                if u.extracted_data_jsonb and isinstance(u.extracted_data_jsonb, dict):
                    for k, v in u.extracted_data_jsonb.items():
                        if v is not None and v != "" and k != "missing_fields":
                            accumulated_criteria[k] = v

            # 3. Contextual extraction with Gemini using full multi-turn conversation
            llm = GeminiAdapter(api_key=settings.GEMINI_API_KEY)
            req = LLMCompletionRequest(
                messages=chat_turns,
                prompt="Extract all cumulative vehicle sourcing criteria from the conversation history and latest message.",
                system_prompt=(
                    "You are an expert automotive export analyst. Extract vehicle make, model, "
                    "year, budget_eur, fuel_type, fcr_eligible, and intent based on the entire conversation context."
                ),
                model=settings.GEMINI_MODEL,
            )
            extracted_obj, _ = await llm.generate_structured_output(
                req, VehicleRequestExtraction
            )

            # Merge new extraction into accumulated criteria
            for k, v in extracted_obj.model_dump().items():
                if v is not None and v != "" and k != "missing_fields":
                    accumulated_criteria[k] = v

            validated_extraction = validate_vehicle_request(accumulated_criteria)
            accumulated_criteria["missing_fields"] = validated_extraction.missing_fields

            # Generate summary for CRM dashboard
            summary_parts = []
            if accumulated_criteria.get("make"):
                summary_parts.append(str(accumulated_criteria["make"]))
            if accumulated_criteria.get("model"):
                summary_parts.append(str(accumulated_criteria["model"]))
            if accumulated_criteria.get("year"):
                summary_parts.append(f"({accumulated_criteria['year']})")
            if accumulated_criteria.get("budget_eur"):
                summary_parts.append(f"- Budget: {accumulated_criteria['budget_eur']}€")
            summary_fr = " ".join(summary_parts) if summary_parts else "Demande d'information véhicule"

            understanding = AIUnderstanding(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                message_id=message_id,
                customer_id=customer_id,
                intent=validated_extraction.intent,
                extracted_data_jsonb=accumulated_criteria,
                confidence_score=0.95,
                status=AIUnderstandingStatus.PROVISIONAL.value,
                detected_language=validated_extraction.language or "fr",
                summary_fr=summary_fr,
                model_name=settings.GEMINI_MODEL,
                prompt_version="v2.0",
            )
            db.add(understanding)
            await db.flush()

            # 4. Generate multi-turn contextual WhatsApp response with Gemini
            if is_first_turn:
                stage_rule = (
                    "CONVERSATION STAGE: INITIAL INCOMING MESSAGE (Turn #1).\n"
                    "You may provide a warm, concise opening greeting (e.g. 'Salem khouya !' or 'Bonjour !') and welcome the customer to our European car export service."
                )
            else:
                stage_rule = (
                    f"CONVERSATION STAGE: ONGOING DIALOG (Turn #{turn_count}).\n"
                    "CRITICAL ANTI-GREETING RULE: Greetings (Salem, Marhba, Bonjour, Bonsoir, Ahla, Hi, Hello, etc.) were ALREADY EXCHANGED earlier in this discussion. "
                    "DO NOT start with ANY greeting, welcoming phrase, or pleasantry! "
                    "DO NOT say 'Salem', 'Bonjour', 'Marhba', 'Bienvenue', or 'Ahla'. "
                    "Start your reply DIRECTLY with the substantive answer, vehicle details, quotation options, or the next clarifying question."
                )

            active_criteria_summary = {
                k: v for k, v in accumulated_criteria.items() if v is not None and v != ""
            }

            reply_system_prompt = (
                "You are the dedicated AI Automotive Export Advisor for a European Car Export CRM to Tunisia.\n"
                "Your mission is to hold a natural, coherent, multi-turn discussion on WhatsApp without human intervention.\n\n"
                f"{stage_rule}\n\n"
                "CORE CONVERSATION & MEMORY RULES:\n"
                f"1. ACCUMULATED SEARCH CRITERIA: {json.dumps(active_criteria_summary, ensure_ascii=False)}\n"
                f"2. STILL MISSING CRITERIA: {validated_extraction.missing_fields}\n"
                "3. MULTI-TURN CONTINUITY: You MUST remember and build upon everything the customer previously mentioned (make, model, year, budget, options, FCR). Never ask for information the customer has already given.\n"
                "4. LANGUAGE & TONE: Mirror the customer's language and dialect (Tunisian Derja, French, Arabic, or English). Keep answers concise, helpful, and formatted for WhatsApp (short paragraphs, clean bullet points, subtle emojis).\n"
                "5. DOMAIN EXPERTISE: Sourcing European stock (Germany, France, Italy) Netto (VAT excluded), Ro-Ro shipping to Port of Rades / La Goulette (7-14 days), FCR customs clearance & tax exemptions, vehicle technical inspection (TÜV/Dekra).\n"
                "6. DIRECT OUTPUT ONLY: Return ONLY the exact text to send to the customer on WhatsApp. No markdown code blocks, thoughts, or meta explanations."
            )

            reply_req = LLMCompletionRequest(
                messages=chat_turns,
                prompt="Respond to the customer message above adhering strictly to the stage and domain rules:",
                system_prompt=reply_system_prompt,
                model=settings.GEMINI_MODEL,
                temperature=0.3,
            )
            reply_res = await llm.generate_text(reply_req)
            draft_reply = reply_res.content.strip()

            # 5. Anti-Greeting Safety Net for subsequent turns
            if not is_first_turn and draft_reply:
                greeting_regex = (
                    r"^(?:salem(?:\s+(?:alikoum|3likom|khouya|si\s+\w+))?|"
                    r"salam(?:\s+(?:alaykoum|3laykom|khouya))?|"
                    r"marhba(?:\s+(?:bik(?:om)?|khouya|si\s+\w+))?|"
                    r"ahla(?:\s+(?:bik(?:om)?|khouya|si\s+\w+|marhba))?|"
                    r"bonjour(?:\s+(?:cher\s+client|si\s+\w+|monsieur|madame))?|"
                    r"bonsoir(?:\s+(?:cher\s+client|si\s+\w+|monsieur|madame))?|"
                    r"hello(?:\s+\w+)?|hi(?:\s+\w+)?|salut(?:\s+\w+)?)"
                    r"[\s,!.:\-–—]*\n*"
                )
                cleaned = re.sub(greeting_regex, "", draft_reply, flags=re.IGNORECASE).strip()
                if cleaned:
                    draft_reply = cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned

            if not draft_reply:
                if accumulated_criteria.get("make") or accumulated_criteria.get("model"):
                    vehicle_str = f"{accumulated_criteria.get('make') or ''} {accumulated_criteria.get('model') or ''}".strip()
                    year_str = f" ({accumulated_criteria.get('year')})" if accumulated_criteria.get('year') else ""
                    budget_str = f" avec un budget de {accumulated_criteria.get('budget_eur')} €" if accumulated_criteria.get('budget_eur') else ""
                    draft_reply = f"Bien noté ! Nous poursuivons la recherche pour votre {vehicle_str}{year_str}{budget_str}. Avez-vous d'autres précisions (ex: boîte automatique, finition, ou FCR) ?"
                else:
                    draft_reply = "Bien reçu ! Quelles sont vos préférences pour votre véhicule (marque, modèle, année ou budget) ?"

            policy = load_agent_policy()
            conv_service = ConversationService(db, tenant_id=tenant_id)
            provider = MetaWhatsAppProvider(
                app_secret=settings.META_WEBHOOK_APP_SECRET,
                access_token=settings.META_WHATSAPP_ACCESS_TOKEN,
                phone_number_id=settings.META_WHATSAPP_PHONE_NUMBER_ID or phone_number_id,
                api_version=settings.META_API_VERSION,
            )

            suggestion_status = AISuggestionStatus.SUGGESTED_NOT_SENT.value

            # Autonomous Auto-Reply dispatch if policy enables auto_reply
            if policy.auto_reply and draft_reply:
                try:
                    target_phone_id = settings.META_WHATSAPP_PHONE_NUMBER_ID or phone_number_id
                    send_res = await provider.send_text_message(
                        phone_number_id=target_phone_id,
                        recipient_e164=from_phone_e164,
                        text_body=draft_reply,
                    )
                    await conv_service.add_message(
                        conversation_id=conversation_id,
                        direction=MessageDirection.OUTBOUND,
                        sender_type=MessageSenderType.AI_BOT,
                        content=draft_reply,
                        provider_message_id=send_res.wamid,
                        message_type="text",
                        delivery_status=MessageDeliveryStatus.SENT,
                    )
                    suggestion_status = AISuggestionStatus.ACCEPTED.value
                    logger.info(
                        "AUTONOMOUS_AI_REPLY_SENT",
                        extra={
                            "conversation_id": str(conversation_id),
                            "recipient": from_phone_e164,
                            "wamid": send_res.wamid,
                        },
                    )
                except Exception as send_err:
                    logger.error(f"Failed to auto-dispatch WhatsApp reply: {send_err}")

            suggestion = AISuggestion(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                customer_id=customer_id,
                understanding_id=understanding.id,
                suggested_text=draft_reply,
                target_language="fr",
                status=suggestion_status,
                model_name=settings.GEMINI_MODEL,
                prompt_version="v2.0",
            )
            db.add(suggestion)
            await db.commit()

            await ws_manager.broadcast_to_tenant(
                tenant_id=tenant_id,
                event_type="INBOX_MESSAGE_RECEIVED",
                data={
                    "conversation_id": str(conversation_id),
                    "action": "AI_AUTO_REPLY_SENT",
                },
            )
        except Exception as bg_err:
            logger.error(f"Error in background AI auto-reply processing: {bg_err}", exc_info=True)


@router.post("/whatsapp")
@router.post("/whatsapp/meta")
async def receive_whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    provider: WhatsAppProvider = Depends(get_whatsapp_provider),
) -> dict[str, Any]:
    """Inbound Meta WhatsApp webhook handler (BR-008).

    1. Signature verified by WebhookSignatureMiddleware.
    2. Payload parsed into normalized WhatsAppMessage DTOs.
    3. Resolves multi-tenant WhatsAppAccount by phone_number_id.
    4. Auto-provisions Customer, Conversation thread, and Message record.
    5. Triggers Google Gemini AI extraction & HITL response draft generation.
    6. Broadcasts real-time WebSocket event to active CRM clients.
    7. Returns HTTP 200 OK (<200ms target).
    """
    from app.models.tenant import Tenant
    from app.services.conversation_service import (
        ConversationService,
        MessageDirection,
        MessageSenderType,
    )
    from app.utils.uuid import generate_uuidv7

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
            # Auto-provision a default WhatsAppAccount if none exists in dev
            stmt_tenant = select(Tenant).limit(1)
            tenant = (await db.execute(stmt_tenant)).scalars().first()
            if tenant:
                account = WhatsAppAccount(
                    id=generate_uuidv7(),
                    tenant_id=tenant.id,
                    phone_number_id=msg.phone_number_id or settings.META_WHATSAPP_PHONE_NUMBER_ID or "1328057297058642",
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

        # Auto-provision or fetch Customer profile
        tenant_id_str = str(account.tenant_id)
        customer_service = CustomerService(db, tenant_id=account.tenant_id)
        customer, _ = await customer_service.get_or_create_by_phone(
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
            await db.flush()

            # Ensure Conversation thread and timeline Message are created
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

            await db.commit()

            # Trigger non-blocking asynchronous AI extraction & Auto-reply in background
            if msg.text_body and msg.text_body.strip() and settings.GEMINI_API_KEY:
                background_tasks.add_task(
                    _process_ai_and_auto_reply,
                    tenant_id=account.tenant_id,
                    conversation_id=conversation.id,
                    customer_id=customer.id,
                    message_id=created_msg.id,
                    from_phone_e164=msg.from_phone_e164,
                    text_body=msg.text_body,
                    phone_number_id=account.phone_number_id,
                )

            from app.core.ws_manager import ws_manager
            await ws_manager.broadcast_to_tenant(
                tenant_id=account.tenant_id,
                event_type="INBOX_MESSAGE_RECEIVED",
                data={
                    "conversation_id": str(conversation.id),
                    "message_id": str(created_msg.id),
                    "content": msg.text_body,
                    "sender_phone": msg.from_phone_e164,
                },
            )

            job_id = await enqueue_inbound_message_job(
                message_id=inbound_record.id,
                tenant_id=account.tenant_id,
            )
            logger.info(
                "Inbound WhatsApp message processed and persisted",
                extra={
                    "inbound_id": str(inbound_record.id),
                    "conversation_id": str(conversation.id),
                    "tenant_id": tenant_id_str,
                    "wamid": msg.wamid,
                    "job_id": job_id,
                },
            )
            results.append(
                {
                    "status": "received",
                    "inbound_message_id": str(inbound_record.id),
                    "conversation_id": str(conversation.id),
                    "wamid": msg.wamid,
                    "job_id": job_id,
                }
            )
        except IntegrityError:
            await db.rollback()
            logger.info(
                "Duplicate wamid payload received, atomic deduplication caught (BR-008)",
                extra={"wamid": msg.wamid, "tenant_id": tenant_id_str},
            )
            results.append(
                {
                    "status": "duplicate_ignored",
                    "wamid": msg.wamid,
                }
            )

    return {"status": "success", "processed_count": len(results), "details": results}
