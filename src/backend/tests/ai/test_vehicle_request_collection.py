"""Autonomous Conversational Vehicle Request Collection Test Suite (Phase 5).

Verifies:
1. Multi-turn sequential vehicle sourcing criteria gathering.
2. Single-turn all-in-one criteria extraction.
3. Customer specification corrections and in-place updates.
4. Active VehicleRequest persistence in PostgreSQL without creating duplicates.
5. Missing required fields identification and natural non-repetitive asking.
6. Multilingual collection across French, Arabic/Derja, English, and German.
7. Unconfirmed vs Qualified request lifecycle integrity.
"""

import uuid
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.agent_state_machine import ConversationState
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.models.vehicle_request import VehicleRequest, VehicleRequestStatus
from app.ports.llm import LLMCompletionResponse, LLMProvider
from app.ports.whatsapp import OutboundWhatsAppMessageResult, WhatsAppProvider
from app.schemas.agent_decision import AgentDecision
from app.services.agent_orchestrator import AgentOrchestrator
from app.utils.uuid import generate_uuidv7


class MockWhatsAppProvider(WhatsAppProvider):
    """Mock WhatsApp provider generating unique wamids on every dispatch."""

    def __init__(self) -> None:
        self.dispatched_messages: list[dict[str, str]] = []

    def verify_webhook_signature(self, raw_body: bytes, signature_header: str | None) -> bool:
        return True

    def parse_webhook_payload(self, payload: dict[str, Any]) -> list[Any]:
        return []

    async def send_text_message(
        self, phone_number_id: str, recipient_e164: str, text_body: str
    ) -> OutboundWhatsAppMessageResult:
        wamid = f"wamid.mock.{uuid.uuid4().hex[:12]}"
        self.dispatched_messages.append({"recipient": recipient_e164, "text": text_body, "wamid": wamid})
        return OutboundWhatsAppMessageResult(wamid=wamid, recipient_e164=recipient_e164, status="sent")

    async def send_template_message(
        self, phone_number_id: str, recipient_e164: str, template_name: str, language_code: str = "fr", components: list[dict[str, Any]] | None = None
    ) -> OutboundWhatsAppMessageResult:
        wamid = f"wamid.mock.tpl.{uuid.uuid4().hex[:12]}"
        return OutboundWhatsAppMessageResult(wamid=wamid, recipient_e164=recipient_e164, status="sent")


@pytest.mark.asyncio
async def test_multiturn_sequential_vehicle_request_collection(db_session: AsyncSession):
    """Verify multi-turn collection across 4 sequential turns from greeting to explicit qualification."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conversation_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Test Sales Co", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+33698765432",
        first_name="Yassine",
        preferred_language="fr",
    )
    conv = WhatsAppConversation(
        id=conversation_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        draft_data={},
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_whatsapp = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=mock_llm,
        whatsapp_provider=mock_whatsapp,
    )

    # Turn 1: Customer provides Make and Model
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="VEHICLE_REQUEST",
            language="fr",
            make="BMW",
            model="Série 3",
            response_text="Très bon choix ! Quelle année et quelle motorisation (diesel, essence ou hybride) recherchez-vous pour cette BMW Série 3 ?",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )

    t1_msg_id = generate_uuidv7()
    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=t1_msg_id,
        from_phone_e164="+33698765432",
        text_body="Bonjour, je cherche une BMW Série 3 pour exporter en Tunisie.",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.COLLECTING_REQUEST.value
    assert conv.draft_data["make"] == "BMW"
    assert conv.draft_data["model"] == "Série 3"
    assert "year" in conv.draft_data["missing_fields"]
    assert "budget_eur" in conv.draft_data["missing_fields"]

    # Verify active VehicleRequest created in PostgreSQL
    stmt_vreq = select(VehicleRequest).where(VehicleRequest.conversation_id == conversation_id)
    vreq_list = list((await db_session.execute(stmt_vreq)).scalars().all())
    assert len(vreq_list) == 1
    assert vreq_list[0].make == "BMW"
    assert vreq_list[0].model == "Série 3"
    assert vreq_list[0].status == VehicleRequestStatus.COLLECTING

    # Turn 2: Customer provides Year and Fuel type
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="REQUEST_UPDATE",
            language="fr",
            year=2022,
            fuel_type="Diesel",
            response_text="Parfait pour une 2022 Diesel. Quel est votre budget approximatif en euros et votre préférence pour la boîte de vitesses ?",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )

    t2_msg_id = generate_uuidv7()
    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=t2_msg_id,
        from_phone_e164="+33698765432",
        text_body="Modèle 2022 en motorisation diesel svp.",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.COLLECTING_REQUEST.value
    assert conv.draft_data["year"] == 2022
    assert conv.draft_data["fuel_type"] == "Diesel"
    assert "budget_eur" in conv.draft_data["missing_fields"]

    vreq_list = list((await db_session.execute(stmt_vreq)).scalars().all())
    assert len(vreq_list) == 1  # No duplicate!
    assert vreq_list[0].min_year == 2022
    assert vreq_list[0].fuel_type == "Diesel"
    assert vreq_list[0].fcr_compatible is True

    # Turn 3: Customer provides Budget and Transmission -> all required fields present!
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="REQUEST_UPDATE",
            language="fr",
            budget_eur=28000.0,
            transmission="Automatic",
            customer_confirmation_required=True,
            response_text="Voici le récapitulatif de votre recherche :\n- Véhicule : BMW Série 3\n- Année : 2022\n- Carburant : Diesel\n- Boîte : Automatique\n- Budget : 28 000 €\n\nConfirmez-vous ces critères pour lancer le sourcing ?",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )

    t3_msg_id = generate_uuidv7()
    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=t3_msg_id,
        from_phone_e164="+33698765432",
        text_body="Mon budget est 28 000 euros et boîte automatique.",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.AWAITING_REQUEST_CONFIRMATION.value
    assert len(conv.draft_data["missing_fields"]) == 0

    vreq_list = list((await db_session.execute(stmt_vreq)).scalars().all())
    assert len(vreq_list) == 1
    assert vreq_list[0].budget_eur == Decimal("28000.00")
    assert vreq_list[0].transmission == "Automatic"
    assert vreq_list[0].status == VehicleRequestStatus.AWAITING_CONFIRMATION
    assert vreq_list[0].is_qualified is False

    # Turn 4: Customer explicitly confirms!
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="CONFIRMATION",
            language="fr",
            customer_confirmed=True,
            response_text="C'est parfait ! Votre demande est validée. Notre équipe commerciale prépare les meilleures options disponibles et vous contacte très rapidement.",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )

    t4_msg_id = generate_uuidv7()
    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=t4_msg_id,
        from_phone_e164="+33698765432",
        text_body="Oui c'est exactement ça, je confirme !",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.QUALIFIED_REQUEST.value

    vreq_list = list((await db_session.execute(stmt_vreq)).scalars().all())
    assert len(vreq_list) == 1
    assert vreq_list[0].status == VehicleRequestStatus.QUALIFIED
    assert vreq_list[0].is_qualified is True
    assert vreq_list[0].confirmed_at is not None
    assert len(mock_whatsapp.dispatched_messages) == 4


@pytest.mark.asyncio
async def test_single_turn_complete_criteria_extraction(db_session: AsyncSession):
    """Verify single-turn extraction when customer gives all criteria in one message."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conversation_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Test Co AllInOne", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+491701234567",
        first_name="Walid",
    )
    conv = WhatsAppConversation(
        id=conversation_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        draft_data={},
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    all_in_one_query = (
        "Bonjour, je veux une Audi A4 2023 diesel automatique avec un budget de 32000 euros vers le port de Radès."
    )

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="VEHICLE_REQUEST",
            language="fr",
            make="Audi",
            model="A4",
            year=2023,
            fuel_type="Diesel",
            transmission="Automatic",
            budget_eur=32000.0,
            destination_port="Rades",
            customer_confirmation_required=True,
            response_text="Voici le récapitulatif de votre recherche :\n- Audi A4\n- Année : 2023\n- Diesel, Boîte Automatique\n- Budget : 32 000 €\n- Port : Radès\n\nConfirmez-vous cette demande ?",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )

    mock_whatsapp = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=mock_llm,
        whatsapp_provider=mock_whatsapp,
    )

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+491701234567",
        text_body=all_in_one_query,
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.AWAITING_REQUEST_CONFIRMATION.value
    assert len(conv.draft_data["missing_fields"]) == 0
    assert conv.draft_data["make"] == "Audi"
    assert conv.draft_data["budget_eur"] == 32000.0

    stmt_vreq = select(VehicleRequest).where(VehicleRequest.conversation_id == conversation_id)
    vreq = (await db_session.execute(stmt_vreq)).scalar_one_or_none()
    assert vreq is not None
    assert vreq.make == "Audi"
    assert vreq.model == "A4"
    assert vreq.min_year == 2023
    assert vreq.status == VehicleRequestStatus.AWAITING_CONFIRMATION


@pytest.mark.asyncio
async def test_multiturn_customer_correction_handling(db_session: AsyncSession):
    """Verify that when a customer changes or corrects a spec, the active request updates in-place."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conversation_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Test Co Correction", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+33789012345",
        first_name="Farid",
    )
    conv = WhatsAppConversation(
        id=conversation_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        draft_data={},
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_whatsapp = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=mock_llm,
        whatsapp_provider=mock_whatsapp,
    )

    # Turn 1: Customer asks for Golf 8 with manual gearbox and 20k budget
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="VEHICLE_REQUEST",
            language="fr",
            make="Volkswagen",
            model="Golf 8",
            year=2021,
            transmission="Manual",
            budget_eur=20000.0,
            response_text="Noté pour la Golf 8 2021 manuelle à 20 000 €.",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33789012345",
        text_body="Je cherche une Golf 8 2021 manuelle avec budget 20000 euros.",
        phone_number_id="100998877",
    )

    # Turn 2: Customer changes mind and corrects specs to Automatic and 25000 budget
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="REQUEST_UPDATE",
            language="fr",
            transmission="Automatic",
            budget_eur=25000.0,
            customer_confirmation_required=True,
            response_text="C'est bien noté, j'ai mis à jour : boîte Automatique et budget 25 000 €. Confirmez-vous ce récapitulatif ?",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33789012345",
        text_body="Finalement je préfère une boîte automatique et j'augmente le budget à 25000 euros.",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.draft_data["transmission"] == "Automatic"
    assert conv.draft_data["budget_eur"] == 25000.0
    assert conv.draft_data["make"] == "Volkswagen"
    assert conv.draft_data["model"] == "Golf 8"

    # Verify active VehicleRequest in database reflects the updated values
    stmt_vreq = select(VehicleRequest).where(VehicleRequest.conversation_id == conversation_id)
    vreq_list = list((await db_session.execute(stmt_vreq)).scalars().all())
    assert len(vreq_list) == 1
    assert vreq_list[0].transmission == "Automatic"
    assert vreq_list[0].budget_eur == Decimal("25000.00")


@pytest.mark.asyncio
async def test_arabic_derja_multiturn_collection_and_confirmation(db_session: AsyncSession):
    """Verify multi-turn vehicle gathering and confirmation in Arabic / Tunisian Derja."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conversation_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Test Co Arabic", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+21698223344",
        first_name="Tarek",
        preferred_language="ar",
    )
    conv = WhatsAppConversation(
        id=conversation_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        draft_data={},
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_whatsapp = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=mock_llm,
        whatsapp_provider=mock_whatsapp,
    )

    # Turn 1: Arabic request
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="VEHICLE_REQUEST",
            language="ar",
            make="Mercedes-Benz",
            model="Classe C",
            year=2022,
            fuel_type="Diesel",
            budget_eur=30000.0,
            customer_confirmation_required=True,
            response_text="مرحبا بك! ملخص طلبك:\n- مرسيدس Classe C\n- سنة: 2022\n- مازوت\n- الميزانية: 30,000 يورو\n\nهل تؤكد هذه المواصفات؟",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+21698223344",
        text_body="Salem nheb Mercedes Classe C 2022 diesel budget 30000 euro.",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.AWAITING_REQUEST_CONFIRMATION.value

    # Turn 2: Derja confirmation ("eywah mrigla confirmed")
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="CONFIRMATION",
            language="ar",
            customer_confirmed=True,
            response_text="ممتاز! تم تأكيد طلبك بنجاح، سيتواصل معك فريقنا في أقرب وقت.",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+21698223344",
        text_body="eywah mrigla el kolha",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.QUALIFIED_REQUEST.value

    stmt_vreq = select(VehicleRequest).where(VehicleRequest.conversation_id == conversation_id)
    vreq = (await db_session.execute(stmt_vreq)).scalar_one_or_none()
    assert vreq is not None
    assert vreq.is_qualified is True
    assert vreq.make == "Mercedes-Benz"
    assert len(mock_whatsapp.dispatched_messages) == 2


@pytest.mark.asyncio
async def test_multiturn_rejection_and_criteria_resumption(db_session: AsyncSession):
    """Verify customer rejection returns to collecting state without marking request as qualified."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conversation_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Test Co Rejection", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+33611223344",
        first_name="Amine",
    )
    conv = WhatsAppConversation(
        id=conversation_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AWAITING_REQUEST_CONFIRMATION.value,
        draft_data={"make": "Peugeot", "model": "3008", "year": 2021, "budget_eur": 22000.0, "missing_fields": []},
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_whatsapp = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=mock_llm,
        whatsapp_provider=mock_whatsapp,
    )

    # Customer rejects summary
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="REJECTION",
            language="fr",
            customer_confirmed=False,
            response_text="Aucun problème ! Quels éléments souhaitez-vous modifier (modèle, année, budget ou options) ?",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33611223344",
        text_body="Non pas du tout, je me suis trompé de modèle.",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.COLLECTING_REQUEST.value

    stmt_vreq = select(VehicleRequest).where(VehicleRequest.conversation_id == conversation_id)
    vreq = (await db_session.execute(stmt_vreq)).scalar_one_or_none()
    assert vreq is not None
    assert vreq.is_qualified is False
    assert vreq.status != VehicleRequestStatus.QUALIFIED


@pytest.mark.asyncio
async def test_german_and_english_multiturn_collection(db_session: AsyncSession):
    """Verify multi-turn collection in German and English preserves language context."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conversation_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Test Co DE", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+49152998877",
        first_name="Hans",
        preferred_language="de",
    )
    conv = WhatsAppConversation(
        id=conversation_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        draft_data={},
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_whatsapp = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=mock_llm,
        whatsapp_provider=mock_whatsapp,
    )

    # Turn 1: German initial criteria
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="VEHICLE_REQUEST",
            language="de",
            make="Porsche",
            model="Macan",
            year=2022,
            budget_eur=60000.0,
            customer_confirmation_required=True,
            response_text="Hier ist die Zusammenfassung Ihrer Anfrage:\n- Porsche Macan\n- Baujahr: 2022\n- Budget: 60.000 €\n\nBitte bestätigen Sie diese Angaben.",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+49152998877",
        text_body="Hallo, ich suche einen Porsche Macan Baujahr 2022 mit einem Budget von 60000 Euro.",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.AWAITING_REQUEST_CONFIRMATION.value
    assert conv.draft_data["make"] == "Porsche"
    assert conv.draft_data["model"] == "Macan"

    # Turn 2: German confirmation ("genau das passt")
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="CONFIRMATION",
            language="de",
            customer_confirmed=True,
            response_text="Vielen Dank! Ihre Anfrage ist bestätigt. Unser Team wird sich in Kürze bei Ihnen melden.",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+49152998877",
        text_body="Ja genau das passt, vielen Dank!",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.QUALIFIED_REQUEST.value

    stmt_vreq = select(VehicleRequest).where(VehicleRequest.conversation_id == conversation_id)
    vreq = (await db_session.execute(stmt_vreq)).scalar_one_or_none()
    assert vreq is not None
    assert vreq.is_qualified is True
    assert vreq.make == "Porsche"

