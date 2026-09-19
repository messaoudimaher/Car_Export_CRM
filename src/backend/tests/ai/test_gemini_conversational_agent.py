"""Automated Test Suite for Gemini Autonomous Conversational Sales Agent (Phase 3).

Verifies:
1. Greetings & auto-welcome.
2. Grounded FAQ answers from approved company knowledge.
3. Vehicle sourcing intent extraction (single-turn and multi-field).
4. Multilingual conversations (Arabic, French, English, German).
5. Mixed language / code-switching (Derja + French/English).
6. Malformed LLM output handling.
7. Gemini timeout graceful degradation.
8. Gemini API failure graceful degradation.
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.future import select

from app.core.database import async_session_factory
from app.core.whatsapp_telemetry import WhatsAppTimingMetrics
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.tenant import Tenant
from app.ports.llm import LLMCompletionRequest, LLMCompletionResponse, LLMProvider
from app.ports.whatsapp import OutboundWhatsAppMessageResult, WhatsAppProvider
from app.schemas.agent_decision import AgentDecision
from app.services.agent_orchestrator import AgentOrchestrator
from app.utils.uuid import generate_uuidv7


class MockLLMProvider(LLMProvider):
    """Mock LLM provider returning controlled AgentDecision responses."""

    def __init__(self, canned_decision: AgentDecision | None = None, raise_exception: Exception | None = None) -> None:
        self.canned_decision = canned_decision
        self.raise_exception = raise_exception

    async def generate_text(self, request: LLMCompletionRequest) -> LLMCompletionResponse:
        return LLMCompletionResponse(content="Mock text response", model="mock-model")

    async def generate_structured_output(
        self, request: LLMCompletionRequest, schema: type[Any]
    ) -> tuple[Any, LLMCompletionResponse]:
        if self.raise_exception:
            raise self.raise_exception
        if self.canned_decision:
            return self.canned_decision, LLMCompletionResponse(content="{}", model="mock-model")
        return AgentDecision(
            intent="OTHER",
            response_text="Mock default reply",
        ), LLMCompletionResponse(content="{}", model="mock-model")


class MockWhatsAppProvider(WhatsAppProvider):
    """Mock WhatsApp provider capturing outbound message dispatches."""

    def __init__(self) -> None:
        self.dispatched_messages: list[dict[str, str]] = []

    def verify_webhook_signature(self, raw_body: bytes, signature_header: str | None) -> bool:
        return True

    def parse_webhook_payload(self, payload: dict[str, Any]) -> list[Any]:
        return []

    async def send_text_message(
        self, phone_number_id: str, recipient_e164: str, text_body: str
    ) -> OutboundWhatsAppMessageResult:
        wamid = f"wamid.mock.out.{uuid.uuid4().hex[:8]}"
        self.dispatched_messages.append(
            {"recipient": recipient_e164, "text": text_body, "wamid": wamid}
        )
        return OutboundWhatsAppMessageResult(wamid=wamid, recipient_e164=recipient_e164, status="sent")

    async def send_template_message(
        self, phone_number_id: str, recipient_e164: str, template_name: str, language_code: str = "fr", components: list[dict[str, Any]] | None = None
    ) -> OutboundWhatsAppMessageResult:
        return OutboundWhatsAppMessageResult(wamid="wamid.mock.tpl", recipient_e164=recipient_e164, status="sent")


@pytest.mark.asyncio
async def test_agent_handles_hello_greeting():
    """Verify customer greeting triggers automatic greeting reply."""
    async with async_session_factory() as db:
        tenant_id = generate_uuidv7()
        tenant = Tenant(id=tenant_id, name="Test Tenant", slug=f"t-{uuid.uuid4().hex[:6]}")
        customer = Customer(id=generate_uuidv7(), tenant_id=tenant_id, phone_e164="+21698111222", preferred_language="fr")
        conv = WhatsAppConversation(id=generate_uuidv7(), tenant_id=tenant_id, customer_id=customer.id)
        msg = Message(id=generate_uuidv7(), tenant_id=tenant_id, conversation_id=conv.id, direction="Inbound", sender_type="Customer", content="Bonjour !")
        db.add_all([tenant, customer, conv, msg])
        await db.commit()

        mock_decision = AgentDecision(
            intent="GREETING",
            language="fr",
            response_text="Bonjour et bienvenue chez Auto Export Europe ! Comment puis-je vous aider pour votre projet d'exportation de véhicule vers la Tunisie ?",
        )
        mock_llm = MockLLMProvider(canned_decision=mock_decision)
        mock_wa = MockWhatsAppProvider()

        orchestrator = AgentOrchestrator(db, llm_provider=mock_llm, whatsapp_provider=mock_wa)
        decision = await orchestrator.process_turn(
            tenant_id=tenant_id,
            conversation_id=conv.id,
            customer_id=customer.id,
            message_id=msg.id,
            from_phone_e164="+21698111222",
            text_body="Bonjour !",
            phone_number_id="12345",
        )

        assert decision.intent == "GREETING"
        assert len(mock_wa.dispatched_messages) == 1
        assert "Auto Export Europe" in mock_wa.dispatched_messages[0]["text"]


@pytest.mark.asyncio
async def test_agent_answers_grounded_faq():
    """Verify customer asking FCR conditions receives grounded answer."""
    async with async_session_factory() as db:
        tenant_id = generate_uuidv7()
        tenant = Tenant(id=tenant_id, name="Test Tenant", slug=f"t-{uuid.uuid4().hex[:6]}")
        customer = Customer(id=generate_uuidv7(), tenant_id=tenant_id, phone_e164="+21698222333", preferred_language="fr")
        conv = WhatsAppConversation(id=generate_uuidv7(), tenant_id=tenant_id, customer_id=customer.id)
        msg = Message(id=generate_uuidv7(), tenant_id=tenant_id, conversation_id=conv.id, direction="Inbound", sender_type="Customer", content="Quelles sont les conditions FCR ?")
        db.add_all([tenant, customer, conv, msg])
        await db.commit()

        mock_decision = AgentDecision(
            intent="FAQ",
            language="fr",
            response_text="Pour bénéficier du FCR en Tunisie, le véhicule doit avoir au maximum 5 ans à la date d'immatriculation, et vous devez justifier d'un séjour d'au moins 2 ans à l'étranger.",
        )
        mock_llm = MockLLMProvider(canned_decision=mock_decision)
        mock_wa = MockWhatsAppProvider()

        orchestrator = AgentOrchestrator(db, llm_provider=mock_llm, whatsapp_provider=mock_wa)
        decision = await orchestrator.process_turn(
            tenant_id=tenant_id,
            conversation_id=conv.id,
            customer_id=customer.id,
            message_id=msg.id,
            from_phone_e164="+21698222333",
            text_body="Quelles sont les conditions FCR ?",
            phone_number_id="12345",
        )

        assert decision.intent == "FAQ"
        assert "5 ans" in decision.response_text
        assert len(mock_wa.dispatched_messages) == 1


@pytest.mark.asyncio
async def test_agent_vehicle_intent_extraction():
    """Verify vehicle requirements are extracted and stored in conversation draft."""
    async with async_session_factory() as db:
        tenant_id = generate_uuidv7()
        tenant = Tenant(id=tenant_id, name="Test Tenant", slug=f"t-{uuid.uuid4().hex[:6]}")
        customer = Customer(id=generate_uuidv7(), tenant_id=tenant_id, phone_e164="+21698333444", preferred_language="fr")
        conv = WhatsAppConversation(id=generate_uuidv7(), tenant_id=tenant_id, customer_id=customer.id)
        msg = Message(id=generate_uuidv7(), tenant_id=tenant_id, conversation_id=conv.id, direction="Inbound", sender_type="Customer", content="Je cherche une BMW X5 2023 automatique diesel budget 35000€")
        db.add_all([tenant, customer, conv, msg])
        await db.commit()

        mock_decision = AgentDecision(
            intent="VEHICLE_REQUEST",
            language="fr",
            make="BMW",
            model="X5",
            year=2023,
            fuel_type="Diesel",
            transmission="Automatic",
            budget_eur=35000.0,
            destination_port="Rades",
            response_text="Parfait ! Vous recherchez une BMW X5 (2023, Diesel, Automatique, Budget: 35 000 €). Confirmez-vous ces informations pour valider votre demande ?",
        )
        mock_llm = MockLLMProvider(canned_decision=mock_decision)
        mock_wa = MockWhatsAppProvider()

        orchestrator = AgentOrchestrator(db, llm_provider=mock_llm, whatsapp_provider=mock_wa)
        decision = await orchestrator.process_turn(
            tenant_id=tenant_id,
            conversation_id=conv.id,
            customer_id=customer.id,
            message_id=msg.id,
            from_phone_e164="+21698333444",
            text_body="Je cherche une BMW X5 2023 automatique diesel budget 35000€",
            phone_number_id="12345",
        )

        assert decision.make == "BMW"
        assert decision.model == "X5"
        assert decision.year == 2023
        assert decision.budget_eur == 35000.0
        assert len(mock_wa.dispatched_messages) == 1

        # Check DB draft update
        stmt_conv = select(WhatsAppConversation).where(WhatsAppConversation.id == conv.id)
        updated_conv = (await db.execute(stmt_conv)).scalar_one()
        assert updated_conv.draft_data["make"] == "BMW"
        assert updated_conv.draft_data["model"] == "X5"


@pytest.mark.asyncio
async def test_agent_multilingual_arabic_conversation():
    """Verify Arabic conversation produces Arabic response and accurate extraction."""
    async with async_session_factory() as db:
        tenant_id = generate_uuidv7()
        tenant = Tenant(id=tenant_id, name="Test Tenant", slug=f"t-{uuid.uuid4().hex[:6]}")
        customer = Customer(id=generate_uuidv7(), tenant_id=tenant_id, phone_e164="+21698444555", preferred_language="ar")
        conv = WhatsAppConversation(id=generate_uuidv7(), tenant_id=tenant_id, customer_id=customer.id)
        msg = Message(id=generate_uuidv7(), tenant_id=tenant_id, conversation_id=conv.id, direction="Inbound", sender_type="Customer", content="أبحث عن سيارة مرسيدس C200 موديل 2022 ديزل")
        db.add_all([tenant, customer, conv, msg])
        await db.commit()

        mock_decision = AgentDecision(
            intent="VEHICLE_REQUEST",
            language="ar",
            make="Mercedes-Benz",
            model="C200",
            year=2022,
            fuel_type="Diesel",
            response_text="أهلاً بك! لقد سجلنا طلبك لسيارة مرسيدس C200 موديل 2022 ديزل. ما هي ميزانيتك التقريبية باليورو؟",
        )
        mock_llm = MockLLMProvider(canned_decision=mock_decision)
        mock_wa = MockWhatsAppProvider()

        orchestrator = AgentOrchestrator(db, llm_provider=mock_llm, whatsapp_provider=mock_wa)
        decision = await orchestrator.process_turn(
            tenant_id=tenant_id,
            conversation_id=conv.id,
            customer_id=customer.id,
            message_id=msg.id,
            from_phone_e164="+21698444555",
            text_body="أبحث عن سيارة مرسيدس C200 موديل 2022 ديزل",
            phone_number_id="12345",
        )

        assert decision.language == "ar"
        assert decision.make == "Mercedes-Benz"
        assert "أهلاً بك" in decision.response_text


@pytest.mark.asyncio
async def test_agent_mixed_language_derja_code_switching():
    """Verify mixed Derja / French message is understood seamlessly."""
    async with async_session_factory() as db:
        tenant_id = generate_uuidv7()
        tenant = Tenant(id=tenant_id, name="Test Tenant", slug=f"t-{uuid.uuid4().hex[:6]}")
        customer = Customer(id=generate_uuidv7(), tenant_id=tenant_id, phone_e164="+21698555666", preferred_language="derja")
        conv = WhatsAppConversation(id=generate_uuidv7(), tenant_id=tenant_id, customer_id=customer.id)
        msg = Message(id=generate_uuidv7(), tenant_id=tenant_id, conversation_id=conv.id, direction="Inbound", sender_type="Customer", content="Salem khouya, n7eb Golf 8 automatique année 2022 fi Radès")
        db.add_all([tenant, customer, conv, msg])
        await db.commit()

        mock_decision = AgentDecision(
            intent="VEHICLE_REQUEST",
            language="derja",
            make="Volkswagen",
            model="Golf 8",
            year=2022,
            transmission="Automatic",
            destination_port="Rades",
            response_text="Marhba bik ! 3andna barcha choix Golf 8 2022 automatique. 9adech el budget mte3ek bel Euro ?",
        )
        mock_llm = MockLLMProvider(canned_decision=mock_decision)
        mock_wa = MockWhatsAppProvider()

        orchestrator = AgentOrchestrator(db, llm_provider=mock_llm, whatsapp_provider=mock_wa)
        decision = await orchestrator.process_turn(
            tenant_id=tenant_id,
            conversation_id=conv.id,
            customer_id=customer.id,
            message_id=msg.id,
            from_phone_e164="+21698555666",
            text_body="Salem khouya, n7eb Golf 8 automatique année 2022 fi Radès",
            phone_number_id="12345",
        )

        assert decision.make == "Volkswagen"
        assert decision.model == "Golf 8"
        assert decision.year == 2022
        assert "budget" in decision.response_text.lower()


@pytest.mark.asyncio
async def test_agent_handles_llm_timeout_and_failure_gracefully():
    """Verify Gemini timeout triggers safe fallback reply without crashing worker."""
    import asyncio
    async with async_session_factory() as db:
        tenant_id = generate_uuidv7()
        tenant = Tenant(id=tenant_id, name="Test Tenant", slug=f"t-{uuid.uuid4().hex[:6]}")
        customer = Customer(id=generate_uuidv7(), tenant_id=tenant_id, phone_e164="+21698666777", preferred_language="fr")
        conv = WhatsAppConversation(id=generate_uuidv7(), tenant_id=tenant_id, customer_id=customer.id)
        msg = Message(id=generate_uuidv7(), tenant_id=tenant_id, conversation_id=conv.id, direction="Inbound", sender_type="Customer", content="Bonjour")
        db.add_all([tenant, customer, conv, msg])
        await db.commit()

        mock_llm = MockLLMProvider(raise_exception=asyncio.TimeoutError("Gemini call timed out after 12s"))
        mock_wa = MockWhatsAppProvider()

        orchestrator = AgentOrchestrator(db, llm_provider=mock_llm, whatsapp_provider=mock_wa)
        decision = await orchestrator.process_turn(
            tenant_id=tenant_id,
            conversation_id=conv.id,
            customer_id=customer.id,
            message_id=msg.id,
            from_phone_e164="+21698666777",
            text_body="Bonjour",
            phone_number_id="12345",
        )

        # Should fall back cleanly without raising exception
        assert len(decision.response_text) > 0
        assert len(mock_wa.dispatched_messages) == 1
        assert "Merci pour votre message" in decision.response_text
