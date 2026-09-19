"""Autonomous AI WhatsApp Sales Agent Orchestrator (Phase 3 Autonomous Agent).

Executes single-pass Gemini structured decision reasoning, validates output with Pydantic,
enforces deterministic state machine transitions, and dispatches automatic WhatsApp responses.
"""

import json
import re
import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from app.adapters.llm_gemini import GeminiAdapter
from app.adapters.whatsapp_meta import MetaWhatsAppProvider
from app.core.agent_state_machine import (
    ConversationMode,
    ConversationState,
    HandoffReason,
    compute_deterministic_state_transition,
    is_complaint_message,
    is_explicit_confirmation,
    is_explicit_rejection,
    is_human_requested,
)
from app.core.config import settings
from app.core.logging import logger
from app.core.whatsapp_telemetry import WhatsAppTimingMetrics
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.vehicle_request import VehicleRequest, VehicleRequestStatus, check_fcr_compliance
from app.ports.llm import LLMCompletionRequest, LLMProvider
from app.ports.whatsapp import WhatsAppProvider
from app.schemas.agent_decision import AgentDecision
from app.schemas.vehicle_request_state import validate_vehicle_criteria
from app.services.company_knowledge import get_cached_grounded_context_prompt, load_company_knowledge
from app.services.conversation_memory import load_bounded_conversation_memory
from app.services.csv_export_service import csv_export_service
from app.services.owner_notifier import OwnerNotificationService


class AgentOrchestrator:
    """Coordinates autonomous AI customer conversations over WhatsApp."""

    def __init__(
        self,
        db: AsyncSession,
        llm_provider: LLMProvider | None = None,
        whatsapp_provider: WhatsAppProvider | None = None,
    ) -> None:
        self.db = db
        self.llm = llm_provider or GeminiAdapter(api_key=settings.GEMINI_API_KEY)
        self.whatsapp = whatsapp_provider or MetaWhatsAppProvider(
            app_secret=settings.META_WEBHOOK_APP_SECRET,
            access_token=settings.META_WHATSAPP_ACCESS_TOKEN,
            phone_number_id=settings.META_WHATSAPP_PHONE_NUMBER_ID,
            api_version=settings.META_API_VERSION,
        )
        self.knowledge = load_company_knowledge()
        self.owner_notifier = OwnerNotificationService(whatsapp_provider=self.whatsapp)

    async def process_turn(
        self,
        tenant_id: uuid.UUID,
        conversation_id: uuid.UUID,
        customer_id: uuid.UUID,
        message_id: uuid.UUID,
        from_phone_e164: str,
        text_body: str,
        phone_number_id: str,
        timing_metrics: WhatsAppTimingMetrics | None = None,
    ) -> AgentDecision:
        """Execute single-pass autonomous reasoning turn and dispatch automatic response."""
        if timing_metrics:
            timing_metrics.mark_db_read_started()

        # 1. High-Performance DB Read: Fetch conversation & customer in a single joined query
        stmt_conv = (
            select(WhatsAppConversation, Customer)
            .join(Customer, Customer.id == WhatsAppConversation.customer_id, isouter=True)
            .where(WhatsAppConversation.id == conversation_id)
        )
        conv_res = await self.db.execute(stmt_conv)
        row = conv_res.first()

        if not row:
            raise ValueError(f"Conversation '{conversation_id}' not found.")

        conversation, customer = row

        # STRICT HUMAN INTERVENTION GATE:
        # When HUMAN_ACTIVE or mode == HUMAN, AI automatic replies MUST STOP.
        if (
            conversation.mode == ConversationMode.HUMAN.value
            or conversation.conversation_state == ConversationState.HUMAN_ACTIVE.value
        ):
            if timing_metrics:
                timing_metrics.mark_db_read_completed()
            logger.info(
                "AGENT_TURN_SKIPPED_HUMAN_ACTIVE",
                extra={"conversation_id": str(conversation_id)},
            )
            return AgentDecision(
                intent="HUMAN_REQUEST",
                response_text="Human representative active.",
            )

        # 2. Assemble bounded memory context reusing preloaded entities
        memory = await load_bounded_conversation_memory(
            self.db,
            conversation_id,
            max_recent_messages=15,
            preloaded_conversation=conversation,
            preloaded_customer=customer,
        )
        if timing_metrics:
            timing_metrics.mark_db_read_completed()

        # 3. Formulate unified single-pass system prompt with cached grounded knowledge
        knowledge_context = get_cached_grounded_context_prompt()
        memory_context = memory.to_system_prompt_context()

        system_prompt = (
            "You are the dedicated Autonomous AI Automotive Sales Agent for 'Auto Export Europe', "
            "specializing in European vehicle sourcing and export to Tunisia.\n"
            "Your objective is to conduct a natural, helpful, and highly competent sales conversation on WhatsApp.\n\n"
            f"{memory_context}\n\n"
            f"{knowledge_context}\n\n"
            "CORE OPERATIONAL RULES:\n"
            "1. MULTILINGUAL SUPPORT: Mirror customer's language/dialect (French, Arabic, Tunisian Derja/Arabizi, English, German). Preserve vehicle terms.\n"
            "2. ZERO FABRICATION: Never invent company policies, guarantees, prices, or offices not stated in knowledge.\n"
            "3. NO BINDING COMMITMENTS: Never invent fixed vehicle prices or guarantee stock availability without confirmation.\n"
            "4. OUT-OF-SCOPE: If customer asks for unverified info (crypto, 10-year warranty, fake offices), state a human advisor will assist, set human_attention_required=true.\n"
            "5. VEHICLE SOURCING FLOW:\n"
            "   - Extract criteria (make, model, year, fuel, transmission, budget, port, options).\n"
            "   - If required criteria are missing (Make, Model, Year, Budget), acknowledge and ask for the next missing field.\n"
            "   - When all required criteria are present, present a structured summary and ask for explicit confirmation.\n"
            "   - If customer asks an FAQ, answer directly using approved knowledge and smoothly continue collection.\n"
            "6. HUMAN ESCALATION: If customer asks for human, has complaint, asks out-of-scope policies, or demands price discounts, set human_attention_required=true.\n"
            "7. DIRECT WHATSAPP OUTPUT: In 'response_text', provide ONLY the clean message to send to the customer on WhatsApp."
        )
        if timing_metrics:
            timing_metrics.mark_context_constructed()

        llm_request = LLMCompletionRequest(
            messages=memory.chat_turns,
            prompt=f"Customer message: '{text_body}'. Analyze intent, extract criteria, and formulate automatic WhatsApp response:",
            system_prompt=system_prompt,
            model=settings.GEMINI_MODEL,
            temperature=0.2,
            timeout_seconds=12.0,
        )

        start_llm = time.perf_counter()
        if timing_metrics:
            timing_metrics.mark_llm_started()

        is_tech_err = False
        try:
            decision, llm_response = await self.llm.generate_structured_output(llm_request, AgentDecision)
            llm_latency_ms = (time.perf_counter() - start_llm) * 1000.0
            logger.info("GEMINI_AGENT_DECISION_SUCCESS", extra={"latency_ms": llm_latency_ms, "intent": decision.intent})
        except Exception as llm_err:
            llm_latency_ms = (time.perf_counter() - start_llm) * 1000.0
            logger.error(f"Gemini API invocation failed ({llm_latency_ms:.1f}ms): {llm_err}", exc_info=True)
            is_tech_err = True
            # Graceful localized escalation fallback message
            lang = memory.preferred_language or "fr"
            if lang == "ar":
                fallback_msg = "حدث خطأ فني مؤقت. سيقوم أحد مستشارينا بالتواصل معك مباشرة في أقرب وقت."
            elif lang == "de":
                fallback_msg = "Ein vorübergehender technischer Fehler ist aufgetreten. Ein Berater wird sich in Kürze persönlich bei Ihnen melden."
            elif lang == "en":
                fallback_msg = "A temporary technical issue occurred. A human advisor will reach out to assist you shortly."
            else:
                fallback_msg = "Un incident technique temporaire est survenu. Un conseiller humain va prendre le relais directement avec vous très rapidement."

            decision = AgentDecision(
                intent="HUMAN_REQUEST",
                language=lang,
                human_attention_required=True,
                human_attention_reason="TECHNICAL_ERROR",
                response_text=fallback_msg,
                reasoning=f"Fallback triggered due to LLM error: {llm_err}",
            )
        finally:
            if timing_metrics:
                timing_metrics.mark_llm_completed()

        # 4. Merge Extracted Vehicle Criteria into Active Draft
        active_draft = dict(conversation.draft_data or {})
        extracted_dict = decision.model_dump(
            exclude={"response_text", "intent", "language", "reasoning", "confidence"}
        )
        for k, v in extracted_dict.items():
            if v is not None and v != "":
                active_draft[k] = v

        validated_state = validate_vehicle_criteria(active_draft)
        active_draft["missing_fields"] = validated_state.missing_fields
        conversation.draft_data = dict(active_draft)
        flag_modified(conversation, "draft_data")
        if timing_metrics:
            timing_metrics.mark_validation_completed()

        # 5. Deterministic State Machine Transition (Human Exceptions Handling)
        has_criteria = bool(active_draft.get("make") or active_draft.get("model"))
        is_unsupported = self.knowledge.is_explicitly_unsupported(text_body) or (
            decision.human_attention_required and (decision.intent == "FAQ" or decision.human_attention_reason == "UNSUPPORTED_QUESTION")
        )
        is_complaint = (
            is_complaint_message(text_body)
            or decision.intent == "COMPLAINT"
            or decision.human_attention_reason == "COMPLAINT"
        )
        is_price_req = (
            any(kw in text_body.lower() for kw in ["prix final", "devis officiel", "remise", "negocier", "rabatt", "discount", "خصم", "تخفيض"])
            or decision.intent == "PRICE_REQUEST"
            or decision.human_attention_reason == "PRICE_REQUEST"
        )
        is_ambiguous = (
            decision.human_attention_reason == "AMBIGUOUS_REQUEST"
            or (decision.confidence < 0.35 and not has_criteria)
            or (decision.intent == "OTHER" and decision.confidence < 0.5 and not has_criteria and len(text_body.split()) > 3)
        )
        wants_human = (
            is_human_requested(text_body)
            or decision.intent == "HUMAN_REQUEST"
            or decision.human_attention_reason == "CUSTOMER_REQUESTED_HUMAN"
            or (
                decision.human_attention_required
                and not (is_unsupported or is_complaint or is_price_req or is_ambiguous or is_tech_err)
            )
        )

        if (is_unsupported or is_complaint or wants_human or is_price_req or is_ambiguous) and not decision.human_attention_required:
            decision.human_attention_required = True

        transition_res = compute_deterministic_state_transition(
            current_state=conversation.conversation_state,
            intent=decision.intent,
            text_body=text_body,
            has_vehicle_criteria=has_criteria,
            missing_fields=validated_state.missing_fields,
            customer_requested_human=wants_human,
            is_price_commitment_request=is_price_req,
            is_unsupported_question=is_unsupported,
            is_complaint=is_complaint,
            is_ambiguous=is_ambiguous,
            is_technical_error=is_tech_err,
        )

        prev_state = conversation.conversation_state
        conversation.conversation_state = transition_res.next_state.value
        if transition_res.handoff_reason:
            conversation.handoff_reason = transition_res.handoff_reason.value
            conversation.handoff_summary = transition_res.summary_note

            # Notify owner of human attention escalation if entering HUMAN_ATTENTION
            if transition_res.next_state == ConversationState.HUMAN_ATTENTION and prev_state != ConversationState.HUMAN_ATTENTION.value:
                await self.owner_notifier.notify_owner_of_human_escalation(
                    tenant_name=self.knowledge.company.name,
                    customer_phone=from_phone_e164,
                    customer_name=memory.customer_name,
                    reason=transition_res.handoff_reason.value,
                    summary=transition_res.summary_note,
                    last_message=text_body,
                    phone_number_id=phone_number_id,
                )

        # 6. Synchronize & Persist Active VehicleRequest in PostgreSQL
        if has_criteria or decision.intent in ("VEHICLE_REQUEST", "REQUEST_UPDATE"):
            stmt_active_vreq = (
                select(VehicleRequest)
                .where(
                    VehicleRequest.conversation_id == conversation_id,
                    VehicleRequest.tenant_id == tenant_id,
                    VehicleRequest.status.in_([
                        VehicleRequestStatus.PENDING,
                        VehicleRequestStatus.COLLECTING,
                        VehicleRequestStatus.AWAITING_CONFIRMATION,
                        VehicleRequestStatus.QUALIFIED,
                    ]),
                )
                .order_by(VehicleRequest.created_at.desc())
            )
            vreq = (await self.db.execute(stmt_active_vreq)).scalar_one_or_none()
            if not vreq:
                vreq = VehicleRequest(
                    tenant_id=tenant_id,
                    customer_id=customer_id,
                    conversation_id=conversation_id,
                    make=str(active_draft.get("make") or "Unspecified"),
                    model=str(active_draft.get("model") or "Unspecified"),
                    status=VehicleRequestStatus.COLLECTING,
                )
                self.db.add(vreq)

            # Update mutable specifications on the active request
            if active_draft.get("make"):
                vreq.make = str(active_draft["make"])
            if active_draft.get("model"):
                vreq.model = str(active_draft["model"])
            if active_draft.get("year"):
                vreq.min_year = int(active_draft["year"])
                vreq.fcr_compatible = check_fcr_compliance(min_year=vreq.min_year)
            if active_draft.get("fuel_type"):
                vreq.fuel_type = str(active_draft["fuel_type"])
            if active_draft.get("transmission"):
                vreq.transmission = str(active_draft["transmission"])
            if active_draft.get("budget_eur"):
                vreq.budget_eur = float(active_draft["budget_eur"])
            if active_draft.get("color"):
                vreq.color = str(active_draft["color"])
            if active_draft.get("max_mileage_km"):
                vreq.max_mileage_km = int(active_draft["max_mileage_km"])
            if active_draft.get("destination_port"):
                vreq.destination_port = str(active_draft["destination_port"])
            if active_draft.get("additional_requirements"):
                vreq.additional_requirements = str(active_draft["additional_requirements"])

            # Update status based on criteria completeness and explicit confirmation
            if transition_res.should_qualify_request:
                was_already_qualified = vreq.is_qualified
                if not was_already_qualified:
                    vreq.mark_as_qualified()
                    # Automatically export to CSV and notify owner (exactly once)
                    csv_export_service.export_qualified_request(
                        request_id=vreq.id,
                        tenant_id=tenant_id,
                        customer_id=customer_id,
                        customer_phone=from_phone_e164,
                        customer_name=memory.customer_name,
                        make=vreq.make,
                        model=vreq.model,
                        year=vreq.min_year,
                        fuel_type=vreq.fuel_type,
                        transmission=vreq.transmission,
                        budget_eur=float(vreq.budget_eur) if vreq.budget_eur is not None else None,
                        destination_port=vreq.destination_port,
                        fcr_compatible=vreq.fcr_compatible,
                        additional_requirements=vreq.additional_requirements,
                        confirmed_at=vreq.confirmed_at,
                    )
                    await self.owner_notifier.notify_owner_of_qualified_request(
                        tenant_name=self.knowledge.company.name,
                        customer_phone=from_phone_e164,
                        customer_name=memory.customer_name,
                        make=vreq.make,
                        model=vreq.model,
                        year=vreq.min_year,
                        fuel_type=vreq.fuel_type,
                        transmission=vreq.transmission,
                        budget_eur=float(vreq.budget_eur) if vreq.budget_eur is not None else None,
                        destination_port=vreq.destination_port,
                        fcr_compatible=vreq.fcr_compatible,
                        additional_requirements=vreq.additional_requirements,
                        confirmed_at=vreq.confirmed_at,
                        phone_number_id=phone_number_id,
                    )
            elif validated_state.is_complete and vreq.status != VehicleRequestStatus.QUALIFIED:
                vreq.status = VehicleRequestStatus.AWAITING_CONFIRMATION
            elif vreq.status != VehicleRequestStatus.QUALIFIED:
                vreq.status = VehicleRequestStatus.COLLECTING

        # 7. Automatic Outbound Response Dispatch via WhatsApp (Safe Failure Isolation)
        draft_reply = decision.response_text.strip()
        if draft_reply:
            if timing_metrics:
                timing_metrics.mark_outbound_started()

            target_phone_id = settings.META_WHATSAPP_PHONE_NUMBER_ID or phone_number_id
            try:
                send_res = await self.whatsapp.send_text_message(
                    phone_number_id=target_phone_id,
                    recipient_e164=from_phone_e164,
                    text_body=draft_reply,
                )
                wamid = send_res.wamid
                delivery_status = "Sent"
            except Exception as send_err:
                logger.error(f"Meta outbound WhatsApp API delivery failed: {send_err}", exc_info=True)
                wamid = f"failed.meta.{uuid.uuid4().hex[:8]}"
                delivery_status = "Failed"

            if timing_metrics:
                timing_metrics.mark_outbound_completed()

            # Record outbound timeline message
            outbound_msg = Message(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                direction="Outbound",
                sender_type="AI_BOT",
                content=draft_reply,
                provider_message_id=wamid,
                message_type="text",
                delivery_status=delivery_status,
            )
            self.db.add(outbound_msg)

        if timing_metrics:
            timing_metrics.mark_db_write_started()

        await self.db.commit()

        if timing_metrics:
            timing_metrics.mark_db_write_completed()
            timing_metrics.log_summary()

        return decision
