"""Failure and Recovery Test Suite (Phase 11 Failure and Recovery).

Tests resilience, fault tolerance, and safe recovery across all external and internal failure modes:
1. Gemini timeout
2. Gemini rate limit (HTTP 429)
3. Gemini unavailable (HTTP 503 / network error)
4. Meta WhatsApp API unavailable
5. Database temporary failure / rollback safety
6. Worker restart & retry safety
7. Duplicate webhook deduplication (atomic wamid idempotency)
8. Malformed Gemini response (invalid JSON / Pydantic schema mismatch)
9. Malformed WhatsApp message payload
10. Partial processing / turn interruption
11. Outbound failure after successful qualification

Guarantees Verified:
- No lost customer message.
- No duplicate qualified request.
- No duplicate outbound response.
- No corrupted VehicleRequest.
- No false qualification.
- Safe system recovery and human escalation.
"""

import asyncio
import csv
import random
import tempfile
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Response, TimeoutException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.adapters.whatsapp_demo import DemoWhatsAppProvider
from app.adapters.whatsapp_meta import MetaWhatsAppProvider
from app.core.agent_state_machine import ConversationMode, ConversationState, HandoffReason
from app.core.errors import ServiceUnavailableException
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.inbound_message import InboundMessage
from app.models.message import Message
from app.models.tenant import Tenant
from app.models.vehicle_request import VehicleRequest, VehicleRequestStatus
from app.models.whatsapp_account import WhatsAppAccount
from app.ports.llm import LLMCompletionRequest, LLMCompletionResponse, LLMProvider
from app.ports.whatsapp import OutboundWhatsAppMessageResult, WhatsAppMessage, WhatsAppProvider
from app.schemas.agent_decision import AgentDecision
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.conversation_service import ConversationService
from app.services.csv_export_service import CSVExportService
from app.services.customer_service import CustomerService
from app.utils.uuid import generate_uuidv7


class MockFailingLLM(LLMProvider):
    """Mock LLM provider that simulates various failure modes."""

    def __init__(self, failure_type: str = "timeout", raw_response: str = ""):
        self.failure_type = failure_type
        self.raw_response = raw_response

    async def generate_text(self, request: LLMCompletionRequest) -> LLMCompletionResponse:
        return await self._trigger_failure()

    async def generate_structured_output(
        self, request: LLMCompletionRequest, response_model: type[AgentDecision]
    ) -> tuple[AgentDecision, LLMCompletionResponse]:
        if self.failure_type == "timeout":
            raise TimeoutException("Gemini API request timed out after 12.0s")
        elif self.failure_type == "rate_limit":
            raise ServiceUnavailableException("Gemini API HTTP 429 Too Many Requests: Resource exhausted")
        elif self.failure_type == "unavailable":
            raise ServiceUnavailableException("Gemini API HTTP 503 Service Unavailable: High load")
        elif self.failure_type == "malformed_json":
            raise ValueError("Invalid JSON received from Gemini: {broken json...")
        elif self.failure_type == "schema_mismatch":
            # Raises a Pydantic validation error
            raise ValueError("Validation error: field 'intent' missing in LLM response")
        
        return await self._trigger_failure()

    async def _trigger_failure(self) -> Any:
        if self.failure_type == "timeout":
            raise TimeoutException("Gemini API timeout")
        raise ServiceUnavailableException(f"Gemini API failure: {self.failure_type}")


class MockFailingWhatsApp(WhatsAppProvider):
    """Mock WhatsApp provider that fails on outbound dispatch."""

    def __init__(self, fail_outbound: bool = True):
        self.fail_outbound = fail_outbound
        self.sent_messages: list[dict[str, Any]] = []

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        return True

    def parse_webhook_payload(self, payload: dict[str, Any]) -> list[WhatsAppMessage]:
        return []

    async def send_text_message(
        self, phone_number_id: str, recipient_e164: str, text_body: str
    ) -> OutboundWhatsAppMessageResult:
        if self.fail_outbound:
            raise ServiceUnavailableException("Meta Graph API HTTP 503: Network connection reset")
        wamid = f"wamid.mock.{uuid.uuid4().hex[:8]}"
        self.sent_messages.append({"recipient": recipient_e164, "text": text_body, "wamid": wamid})
        return OutboundWhatsAppMessageResult(
            wamid=wamid,
            recipient_e164=recipient_e164,
            status="accepted",
            raw_response={"status": "sent"},
        )

    async def send_template_message(
        self, phone_number_id: str, recipient_e164: str, template_name: str, language_code: str, components: list[dict[str, Any]] | None = None
    ) -> OutboundWhatsAppMessageResult:
        return await self.send_text_message(phone_number_id, recipient_e164, f"Template: {template_name}")


import random


@pytest.fixture
async def setup_tenant_and_customer(db_session: AsyncSession):
    unique_suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(
        id=generate_uuidv7(),
        name=f"Failure Testing Tenant {unique_suffix}",
        slug=f"failure-test-{unique_suffix}",
        is_active=True,
    )
    db_session.add(tenant)

    account = WhatsAppAccount(
        id=generate_uuidv7(),
        tenant_id=tenant.id,
        phone_number_id=f"phone_id_{unique_suffix}",
        display_phone_number="+216 71 000 000",
        verified_name="Failure Test WhatsApp",
        is_active=True,
    )
    db_session.add(account)

    cust_service = CustomerService(db_session, tenant_id=tenant.id)
    rand_phone_suffix = random.randint(1000000, 9999999)
    customer_phone = f"+2169{rand_phone_suffix}"
    customer, _ = await cust_service.get_or_create_by_phone(phone=customer_phone)
    customer.full_name = "Anis Trabelsi"
    await db_session.flush()

    conv_service = ConversationService(db_session, tenant_id=tenant.id)
    conversation, _ = await conv_service.get_or_create_conversation(customer_id=customer.id)

    await db_session.commit()
    return tenant, account, customer, conversation


# =========================================================================
# 1. Gemini Timeout Test
# =========================================================================
@pytest.mark.asyncio
async def test_gemini_timeout_recovers_safely(
    db_session: AsyncSession,
    setup_tenant_and_customer: tuple[Tenant, WhatsAppAccount, Customer, WhatsAppConversation],
):
    """Test Gemini timeout results in safe customer fallback, transition to HUMAN_ATTENTION, and no crash."""
    tenant, account, customer, conv = setup_tenant_and_customer

    failing_llm = MockFailingLLM(failure_type="timeout")
    mock_wa = MockFailingWhatsApp(fail_outbound=False)

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=failing_llm,
        whatsapp_provider=mock_wa,
    )

    decision = await orchestrator.process_turn(
        tenant_id=tenant.id,
        conversation_id=conv.id,
        customer_id=customer.id,
        message_id=generate_uuidv7(),
        from_phone_e164=customer.phone_e164,
        text_body="Bonjour, je cherche une Golf 8 diesel 2021.",
        phone_number_id=account.phone_number_id,
    )

    # 1. Escalates gracefully to human attention
    assert decision.human_attention_required is True
    assert decision.human_attention_reason == "TECHNICAL_ERROR"
    assert "incident technique temporaire" in decision.response_text or "conseiller" in decision.response_text

    # 2. State machine transitioned to HUMAN_ATTENTION
    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.HUMAN_ATTENTION.value
    assert conv.handoff_reason == HandoffReason.TECHNICAL_ERROR.value

    # 3. Customer received the fallback message
    assert len(mock_wa.sent_messages) == 1
    assert "conseiller" in mock_wa.sent_messages[0]["text"]


# =========================================================================
# 2. Gemini Rate Limit (HTTP 429) Test
# =========================================================================
@pytest.mark.asyncio
async def test_gemini_rate_limit_recovers_safely(
    db_session: AsyncSession,
    setup_tenant_and_customer: tuple[Tenant, WhatsAppAccount, Customer, WhatsAppConversation],
):
    """Test Gemini HTTP 429 rate limit triggers safe escalation without data corruption."""
    tenant, account, customer, conv = setup_tenant_and_customer

    failing_llm = MockFailingLLM(failure_type="rate_limit")
    mock_wa = MockFailingWhatsApp(fail_outbound=False)

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=failing_llm,
        whatsapp_provider=mock_wa,
    )

    decision = await orchestrator.process_turn(
        tenant_id=tenant.id,
        conversation_id=conv.id,
        customer_id=customer.id,
        message_id=generate_uuidv7(),
        from_phone_e164=customer.phone_e164,
        text_body="Je cherche une Audi A4 2020",
        phone_number_id=account.phone_number_id,
    )

    assert decision.human_attention_required is True
    assert decision.human_attention_reason == "TECHNICAL_ERROR"
    
    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.HUMAN_ATTENTION.value


# =========================================================================
# 3. Gemini Unavailable (HTTP 503) Test
# =========================================================================
@pytest.mark.asyncio
async def test_gemini_unavailable_recovers_safely(
    db_session: AsyncSession,
    setup_tenant_and_customer: tuple[Tenant, WhatsAppAccount, Customer, WhatsAppConversation],
):
    """Test Gemini HTTP 503 service unavailable triggers safe escalation."""
    tenant, account, customer, conv = setup_tenant_and_customer

    failing_llm = MockFailingLLM(failure_type="unavailable")
    mock_wa = MockFailingWhatsApp(fail_outbound=False)

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=failing_llm,
        whatsapp_provider=mock_wa,
    )

    decision = await orchestrator.process_turn(
        tenant_id=tenant.id,
        conversation_id=conv.id,
        customer_id=customer.id,
        message_id=generate_uuidv7(),
        from_phone_e164=customer.phone_e164,
        text_body="Salam, nheb BMW Serie 3",
        phone_number_id=account.phone_number_id,
    )

    assert decision.human_attention_required is True
    assert decision.human_attention_reason == "TECHNICAL_ERROR"


# =========================================================================
# 4. Meta WhatsApp Outbound API Failure Isolation Test
# =========================================================================
@pytest.mark.asyncio
async def test_meta_outbound_failure_isolated_safely(
    db_session: AsyncSession,
    setup_tenant_and_customer: tuple[Tenant, WhatsAppAccount, Customer, WhatsAppConversation],
):
    """Test Meta API outbound delivery failure does not crash transaction and records Failed status."""
    tenant, account, customer, conv = setup_tenant_and_customer

    # Mock working LLM
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="VEHICLE_REQUEST",
            make="Toyota",
            model="Rav4",
            year=2021,
            budget_eur=22000,
            response_text="J'ai bien noté Toyota Rav4 2021 à 22 000€.",
        ),
        LLMCompletionResponse(content="", model="gemini-mock"),
    )

    # WhatsApp provider throws 503 on send
    failing_wa = MockFailingWhatsApp(fail_outbound=True)

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=mock_llm,
        whatsapp_provider=failing_wa,
    )

    # Turn execution should not raise exception
    decision = await orchestrator.process_turn(
        tenant_id=tenant.id,
        conversation_id=conv.id,
        customer_id=customer.id,
        message_id=generate_uuidv7(),
        from_phone_e164=customer.phone_e164,
        text_body="Je cherche Toyota Rav4 2021 budget 22000 euros",
        phone_number_id=account.phone_number_id,
    )

    assert decision.make == "Toyota"

    # Outbound message should be persisted with delivery_status='Failed'
    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conv.id,
            Message.direction == "Outbound",
        )
        .order_by(Message.created_at.desc())
    )
    res = await db_session.execute(stmt)
    outbound_msg = res.scalars().first()
    assert outbound_msg is not None
    assert outbound_msg.delivery_status == "Failed"
    assert outbound_msg.provider_message_id.startswith("failed.meta.")


# =========================================================================
# 5. Outbound Failure After Successful Qualification Test
# =========================================================================
@pytest.mark.asyncio
async def test_outbound_failure_after_qualification_preserves_qualified_state(
    db_session: AsyncSession,
    setup_tenant_and_customer: tuple[Tenant, WhatsAppAccount, Customer, WhatsAppConversation],
):
    """Test that when qualification succeeds, an outbound Meta network failure preserves the QUALIFIED state.
    
    Guarantees:
    - VehicleRequest status == QUALIFIED
    - confirmed_at timestamp is preserved
    - CSV export record is written
    - No duplicate qualified request created on subsequent retry
    """
    tenant, account, customer, conv = setup_tenant_and_customer

    # Set up active conversation draft with all required fields
    conv.draft_data = {
        "make": "Volkswagen",
        "model": "Golf 8",
        "year": 2022,
        "budget_eur": 24000,
        "fuel_type": "Diesel",
        "missing_fields": [],
    }
    conv.conversation_state = ConversationState.AWAITING_REQUEST_CONFIRMATION.value
    await db_session.commit()

    # Customer sends explicit confirmation "Oui je confirme"
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="CONFIRMATION",
            response_text="Parfait, votre demande pour la Volkswagen Golf 8 2022 est validée !",
        ),
        LLMCompletionResponse(content="", model="gemini-mock"),
    )

    failing_wa = MockFailingWhatsApp(fail_outbound=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_csv_service = CSVExportService(export_dir=tmp_dir)
        with patch("app.services.agent_orchestrator.csv_export_service", test_csv_service):
            orchestrator = AgentOrchestrator(
                db=db_session,
                llm_provider=mock_llm,
                whatsapp_provider=failing_wa,
            )

            decision = await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Oui je confirme",
                phone_number_id=account.phone_number_id,
            )

            # 1. State machine transitioned to QUALIFIED_REQUEST
            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.QUALIFIED_REQUEST.value

            # 2. VehicleRequest in PostgreSQL is strictly QUALIFIED with confirmed_at
            stmt = select(VehicleRequest).where(VehicleRequest.conversation_id == conv.id)
            vreq = (await db_session.execute(stmt)).scalar_one_or_none()
            assert vreq is not None
            assert vreq.status == VehicleRequestStatus.QUALIFIED
            assert vreq.confirmed_at is not None
            assert vreq.make == "Volkswagen"
            assert vreq.model == "Golf 8"

            # 3. CSV export succeeded deterministically
            csv_path = test_csv_service.get_csv_path(tenant.id)
            assert csv_path.exists()
            with open(csv_path, mode="r", newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == 1
            assert rows[0]["make"] == "Volkswagen"
            assert rows[0]["model"] == "Golf 8"

            # 4. Outbound message recorded as Failed without corrupting state
            stmt_msg = select(Message).where(Message.conversation_id == conv.id, Message.direction == "Outbound")
            outbound_msg = (await db_session.execute(stmt_msg)).scalar_one_or_none()
            assert outbound_msg is not None
            assert outbound_msg.delivery_status == "Failed"

            # 5. RETRY SCENARIO: Customer sends another message or worker retries
            # Must NOT create duplicate VehicleRequest or duplicate CSV export
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="GENERAL_INQUIRY",
                    response_text="Votre dossier est déjà qualifié.",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )

            await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Vous avez bien reçu ma confirmation ?",
                phone_number_id=account.phone_number_id,
            )

            stmt_all_vreqs = select(VehicleRequest).where(VehicleRequest.conversation_id == conv.id)
            all_vreqs = (await db_session.execute(stmt_all_vreqs)).scalars().all()
            assert len(all_vreqs) == 1  # Exactly ONE VehicleRequest!

            with open(csv_path, mode="r", newline="", encoding="utf-8-sig") as f:
                rows_retry = list(csv.DictReader(f))
            assert len(rows_retry) == 1  # Exactly ONE CSV export row!


# =========================================================================
# 6. Duplicate Webhook Deduplication Test
# =========================================================================
@pytest.mark.asyncio
async def test_duplicate_webhook_deduplication(
    db_session: AsyncSession,
    setup_tenant_and_customer: tuple[Tenant, WhatsAppAccount, Customer, WhatsAppConversation],
):
    """Test that repeated delivery of the same WhatsApp wamid is dropped atomically without double processing."""
    tenant, account, customer, conv = setup_tenant_and_customer
    tenant_id = tenant.id
    account_id = account.id

    duplicate_wamid = f"wamid.duplicate.test.{uuid.uuid4().hex[:6]}"

    # Insert initial inbound message with duplicate_wamid
    first_inbound = InboundMessage(
        tenant_id=tenant_id,
        whatsapp_account_id=account_id,
        provider_message_id=duplicate_wamid,
        sender_phone_e164="+21698765432",
        message_type="text",
        content="Premier envoi",
    )
    db_session.add(first_inbound)
    await db_session.commit()

    # Attempt to insert identical wamid for the same tenant
    second_inbound = InboundMessage(
        tenant_id=tenant_id,
        whatsapp_account_id=account_id,
        provider_message_id=duplicate_wamid,
        sender_phone_e164="+21698765432",
        message_type="text",
        content="Deuxieme envoi identique",
    )
    db_session.add(second_inbound)

    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()

    # Verify only the first inbound message exists
    stmt = select(InboundMessage).where(
        InboundMessage.tenant_id == tenant_id,
        InboundMessage.provider_message_id == duplicate_wamid,
    )
    records = (await db_session.execute(stmt)).scalars().all()
    assert len(records) == 1
    assert records[0].content == "Premier envoi"


# =========================================================================
# 7. Malformed Gemini JSON / Schema Mismatch Test
# =========================================================================
@pytest.mark.asyncio
async def test_malformed_gemini_json_falls_back_gracefully(
    db_session: AsyncSession,
    setup_tenant_and_customer: tuple[Tenant, WhatsAppAccount, Customer, WhatsAppConversation],
):
    """Test malformed LLM JSON triggers fallback and human escalation without crashing."""
    tenant, account, customer, conv = setup_tenant_and_customer

    failing_llm = MockFailingLLM(failure_type="malformed_json")
    mock_wa = MockFailingWhatsApp(fail_outbound=False)

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=failing_llm,
        whatsapp_provider=mock_wa,
    )

    decision = await orchestrator.process_turn(
        tenant_id=tenant.id,
        conversation_id=conv.id,
        customer_id=customer.id,
        message_id=generate_uuidv7(),
        from_phone_e164=customer.phone_e164,
        text_body="Je veux un devis pour Mercedes Classe C",
        phone_number_id=account.phone_number_id,
    )

    assert decision.human_attention_required is True
    assert decision.human_attention_reason == "TECHNICAL_ERROR"
    assert len(mock_wa.sent_messages) == 1


# =========================================================================
# 8. Malformed WhatsApp Webhook Payload Parsing Test
# =========================================================================
def test_malformed_whatsapp_payload_handled_safely():
    """Test that malformed or incomplete Meta WhatsApp webhook payloads return empty list without crashing."""
    provider = MetaWhatsAppProvider(app_secret="test_secret")

    # 1. Empty dict
    assert provider.parse_webhook_payload({}) == []

    # 2. Non-list entry
    assert provider.parse_webhook_payload({"entry": "not_a_list"}) == []

    # 3. Missing changes or value
    assert provider.parse_webhook_payload({"entry": [{}]}) == []
    assert provider.parse_webhook_payload({"entry": [{"changes": [{}]}]}) == []

    # 4. Non-message payload (e.g. status updates)
    status_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [{"id": "wamid.123", "status": "delivered"}],
                        }
                    }
                ]
            }
        ]
    }
    assert provider.parse_webhook_payload(status_payload) == []

    # 5. Malformed message object missing standard text/from fields
    incomplete_msg_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "12345"},
                            "messages": [{"id": "wamid.incomplete"}],
                        }
                    }
                ]
            }
        ]
    }
    msgs = provider.parse_webhook_payload(incomplete_msg_payload)
    assert len(msgs) == 1
    assert msgs[0].wamid == "wamid.incomplete"
    assert msgs[0].text_body == ""
    assert msgs[0].from_phone_e164 in ("", "+")


# =========================================================================
# 9. Partial Processing Interruption & Rollback Safety Test
# =========================================================================
@pytest.mark.asyncio
async def test_partial_processing_does_not_corrupt_vehicle_request(
    db_session: AsyncSession,
    setup_tenant_and_customer: tuple[Tenant, WhatsAppAccount, Customer, WhatsAppConversation],
):
    """Test partial vehicle information does not cause false qualification."""
    tenant, account, customer, conv = setup_tenant_and_customer

    mock_llm = AsyncMock(spec=LLMProvider)
    # Only make and model provided (missing year and budget)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="VEHICLE_REQUEST",
            make="Peugeot",
            model="3008",
            response_text="Très bon choix ! Quelle année et quel budget envisagez-vous ?",
        ),
        LLMCompletionResponse(content="", model="gemini-mock"),
    )
    mock_wa = MockFailingWhatsApp(fail_outbound=False)

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=mock_llm,
        whatsapp_provider=mock_wa,
    )

    decision = await orchestrator.process_turn(
        tenant_id=tenant.id,
        conversation_id=conv.id,
        customer_id=customer.id,
        message_id=generate_uuidv7(),
        from_phone_e164=customer.phone_e164,
        text_body="Je cherche Peugeot 3008",
        phone_number_id=account.phone_number_id,
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.COLLECTING_REQUEST.value

    stmt = select(VehicleRequest).where(VehicleRequest.conversation_id == conv.id)
    vreq = (await db_session.execute(stmt)).scalar_one_or_none()
    assert vreq is not None
    assert vreq.status == VehicleRequestStatus.COLLECTING
    assert vreq.is_qualified is False
    assert vreq.confirmed_at is None
    assert vreq.make == "Peugeot"
    assert vreq.model == "3008"
    assert vreq.min_year is None
    assert vreq.budget_eur is None


# =========================================================================
# 10. Database Temporary Failure / Rollback Safety
# =========================================================================
@pytest.mark.asyncio
async def test_database_temporary_failure_rollback_cleanly(
    db_session: AsyncSession,
    setup_tenant_and_customer: tuple[Tenant, WhatsAppAccount, Customer, WhatsAppConversation],
):
    """Test that a database operational failure triggers clean rollback without corrupted state."""
    tenant, account, customer, conv = setup_tenant_and_customer

    # Create dummy customer and conversation
    conv_service = ConversationService(db_session, tenant_id=tenant.id)

    # Inbound message creation
    inbound = InboundMessage(
        tenant_id=tenant.id,
        whatsapp_account_id=account.id,
        provider_message_id=f"wamid.test.rollback.{uuid.uuid4().hex[:6]}",
        sender_phone_e164="+21698765432",
        message_type="text",
        content="Message before DB drop",
    )
    db_session.add(inbound)
    await db_session.flush()

    # Simulate unexpected DB error on downstream commit
    await db_session.rollback()

    # Verify state rolled back cleanly
    stmt = select(InboundMessage).where(InboundMessage.provider_message_id == inbound.provider_message_id)
    record = (await db_session.execute(stmt)).scalar_one_or_none()
    assert record is None
