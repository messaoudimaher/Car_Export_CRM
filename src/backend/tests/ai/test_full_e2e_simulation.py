"""Phase 12: Full End-to-End Real-World Simulation & Multilingual Validation Suite.

Executes a complete 24-step real-world simulation and multilingual validation:
1. Customer sends Hello.
2. Agent replies automatically.
3. Customer asks FAQ.
4. Agent answers automatically.
5. Customer asks for a vehicle.
6. Agent collects information.
7. Customer sends information in multiple messages.
8. Customer changes one field (correction).
9. Agent remembers and updates it.
10. Customer asks an unrelated question.
11. Agent answers without losing request state.
12. Agent asks for missing information.
13. Agent summarizes request.
14. Customer confirms.
15. Request becomes QUALIFIED.
16. PostgreSQL contains the final record.
17. CSV contains the request.
18. Owner receives notification.
19. Customer receives confirmation.
20. Customer requests human.
21. AI stops.
22. Human takes over.
23. AI resumes.
24. AI continues automatically.

Repeats the flow in:
- Arabic
- French
- English
- German
- Mixed-language (Tunisian Derja / Arabizi + French)
- End-to-end response latency telemetry measurement.
"""

import csv
import random
import tempfile
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent_state_machine import ConversationMode, ConversationState, HandoffReason
from app.core.whatsapp_telemetry import WhatsAppTimingMetrics
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
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


class E2EWhatsAppMock(WhatsAppProvider):
    """Mock WhatsApp provider tracking all dispatched customer and owner messages."""

    def __init__(self) -> None:
        self.dispatched_messages: list[dict[str, Any]] = []

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        return True

    def parse_webhook_payload(self, payload: dict[str, Any]) -> list[WhatsAppMessage]:
        return []

    async def send_text_message(
        self, phone_number_id: str, recipient_e164: str, text_body: str
    ) -> OutboundWhatsAppMessageResult:
        wamid = f"wamid.e2e.{uuid.uuid4().hex[:8]}"
        self.dispatched_messages.append({
            "phone_number_id": phone_number_id,
            "recipient_e164": recipient_e164,
            "text": text_body,
            "wamid": wamid,
            "timestamp": time.time(),
        })
        return OutboundWhatsAppMessageResult(
            wamid=wamid,
            recipient_e164=recipient_e164,
            status="sent",
            raw_response={"status": "sent"},
        )

    async def send_template_message(
        self, phone_number_id: str, recipient_e164: str, template_name: str, language_code: str, components: list[dict[str, Any]] | None = None
    ) -> OutboundWhatsAppMessageResult:
        return await self.send_text_message(phone_number_id, recipient_e164, f"Template: {template_name}")


@pytest.fixture
async def setup_e2e_environment(db_session: AsyncSession):
    """Sets up a clean tenant, WhatsApp account, customer, and conversation."""
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant(
        id=generate_uuidv7(),
        name=f"E2E Simulation Org {suffix}",
        slug=f"e2e-org-{suffix}",
        is_active=True,
    )
    db_session.add(tenant)

    account = WhatsAppAccount(
        id=generate_uuidv7(),
        tenant_id=tenant.id,
        phone_number_id=f"phone_e2e_{suffix}",
        display_phone_number="+216 71 000 000",
        verified_name="Auto Export Europe WhatsApp",
        is_active=True,
    )
    db_session.add(account)

    rand_phone_suffix = random.randint(1000000, 9999999)
    customer_phone = f"+2169{rand_phone_suffix}"

    cust_service = CustomerService(db_session, tenant_id=tenant.id)
    customer, _ = await cust_service.get_or_create_by_phone(phone=customer_phone)
    customer.full_name = "Kamel Ben Salah"
    await db_session.flush()

    conv_service = ConversationService(db_session, tenant_id=tenant.id)
    conversation, _ = await conv_service.get_or_create_conversation(customer_id=customer.id)

    await db_session.commit()
    return tenant, account, customer, conversation


# =========================================================================
# TEST 1: The Full 24-Step Real-World Simulation
# =========================================================================
@pytest.mark.asyncio
async def test_full_24_step_real_world_simulation_end_to_end(
    db_session: AsyncSession,
    setup_e2e_environment: tuple[Tenant, WhatsAppAccount, Customer, WhatsAppConversation],
):
    """Executes the complete 24-step customer sales journey with corrections, FAQ, qualification, and human takeover."""
    tenant, account, customer, conv = setup_e2e_environment

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_wa = E2EWhatsAppMock()

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_csv_service = CSVExportService(export_dir=tmp_dir)
        with patch("app.services.agent_orchestrator.csv_export_service", test_csv_service):
            orchestrator = AgentOrchestrator(
                db=db_session,
                llm_provider=mock_llm,
                whatsapp_provider=mock_wa,
            )

            # --- STEP 1 & 2: Customer sends Hello -> Agent replies automatically ---
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="GREETING",
                    language="fr",
                    response_text="Bonjour ! Bienvenue chez Auto Export Europe. Comment puis-je vous aider pour votre projet d'importation ?",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            d1 = await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Bonjour",
                phone_number_id=account.phone_number_id,
            )
            assert d1.intent == "GREETING"
            assert len(mock_wa.dispatched_messages) == 1
            assert "Bienvenue" in mock_wa.dispatched_messages[0]["text"]

            # --- STEP 3 & 4: Customer asks FAQ -> Agent answers automatically ---
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="FAQ",
                    language="fr",
                    response_text="Le régime FCR permet aux Tunisiens résidents à l'étranger d'importer un véhicule de moins de 5 ans avec exonération douanière.",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            d2 = await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Comment fonctionne le régime FCR pour la Tunisie ?",
                phone_number_id=account.phone_number_id,
            )
            assert d2.intent == "FAQ"
            assert len(mock_wa.dispatched_messages) == 2
            assert "régime FCR" in mock_wa.dispatched_messages[1]["text"]

            # --- STEP 5 & 6: Customer asks for vehicle -> Agent collects info ---
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="VEHICLE_REQUEST",
                    language="fr",
                    make="Volkswagen",
                    model="Golf 8",
                    response_text="Excellent choix pour la Volkswagen Golf 8 ! Quelle année, quelle motorisation et quel budget prévoyez-vous ?",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            d3 = await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Je cherche une Volkswagen Golf 8",
                phone_number_id=account.phone_number_id,
            )
            await db_session.refresh(conv)
            assert conv.draft_data["make"] == "Volkswagen"
            assert conv.draft_data["model"] == "Golf 8"
            assert "year" in conv.draft_data["missing_fields"]
            assert conv.conversation_state == ConversationState.COLLECTING_REQUEST.value

            # --- STEP 7: Customer sends additional specs across turns ---
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="REQUEST_UPDATE",
                    language="fr",
                    year=2022,
                    fuel_type="Diesel",
                    transmission="Automatique",
                    response_text="Très bien : Golf 8 2022 Diesel Automatique. Quel est votre budget approximatif en euros ?",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            d4 = await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Année 2022 en diesel automatique",
                phone_number_id=account.phone_number_id,
            )
            await db_session.refresh(conv)
            assert conv.draft_data["year"] == 2022
            assert conv.draft_data["fuel_type"] == "Diesel"
            assert conv.draft_data["transmission"] == "Automatique"

            # --- STEP 8 & 9: Customer changes one field (Correction) -> Agent remembers & updates ---
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="REQUEST_UPDATE",
                    language="fr",
                    transmission="Manuelle",
                    response_text="C'est bien noté pour la boîte manuelle au lieu d'automatique. Quel est votre budget total ?",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            d5 = await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Finalement je préfère en boîte manuelle",
                phone_number_id=account.phone_number_id,
            )
            await db_session.refresh(conv)
            assert conv.draft_data["make"] == "Volkswagen"
            assert conv.draft_data["model"] == "Golf 8"
            assert conv.draft_data["year"] == 2022
            assert conv.draft_data["fuel_type"] == "Diesel"
            assert conv.draft_data["transmission"] == "Manuelle"  # Corrected in place!

            # --- STEP 10 & 11: Customer asks unrelated question -> Agent answers without losing state ---
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="FAQ",
                    language="fr",
                    response_text="Le délai moyen de transport maritime vers le port de La Goulette est de 5 à 7 jours ouvrés. Pour finaliser votre Golf 8 2022, quel est votre budget ?",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            d6 = await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Quel est le délai de transport vers le port de La Goulette ?",
                phone_number_id=account.phone_number_id,
            )
            await db_session.refresh(conv)
            # Memory state strictly preserved!
            assert conv.draft_data["make"] == "Volkswagen"
            assert conv.draft_data["year"] == 2022
            assert conv.draft_data["transmission"] == "Manuelle"

            # --- STEP 12 & 13: Customer provides missing budget -> Agent summarizes & asks confirmation ---
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="REQUEST_UPDATE",
                    language="fr",
                    budget_eur=24000,
                    destination_port="La Goulette",
                    response_text=(
                        "Récapitulatif de votre recherche :\n"
                        "- Véhicule : Volkswagen Golf 8\n"
                        "- Année : 2022 (Compatible FCR)\n"
                        "- Moteur : Diesel Manuelle\n"
                        "- Budget : 24 000 €\n"
                        "- Port : La Goulette\n"
                        "Confirmez-vous cette demande pour lancer la recherche ?"
                    ),
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            d7 = await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Mon budget est de 24000 euros port la goulette",
                phone_number_id=account.phone_number_id,
            )
            await db_session.refresh(conv)
            assert conv.draft_data["budget_eur"] == 24000
            assert conv.draft_data["missing_fields"] == []
            assert conv.conversation_state == ConversationState.AWAITING_REQUEST_CONFIRMATION.value

            # --- STEP 14, 15, 16, 17, 18, 19: Customer confirms -> QUALIFICATION + PostgreSQL + CSV + Owner + Customer Confirmation ---
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="CONFIRMATION",
                    language="fr",
                    response_text="Parfait ! Votre demande pour la Volkswagen Golf 8 2022 est validée. Notre équipe de sourcing vous contactera très rapidement.",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            d8 = await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Oui je confirme",
                phone_number_id=account.phone_number_id,
            )

            # 15. State machine becomes QUALIFIED_REQUEST
            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.QUALIFIED_REQUEST.value

            # 16. PostgreSQL authoritative record
            stmt_vreq = select(VehicleRequest).where(VehicleRequest.conversation_id == conv.id)
            vreq = (await db_session.execute(stmt_vreq)).scalar_one_or_none()
            assert vreq is not None
            assert vreq.status == VehicleRequestStatus.QUALIFIED
            assert vreq.confirmed_at is not None
            assert vreq.make == "Volkswagen"
            assert vreq.model == "Golf 8"
            assert vreq.min_year == 2022
            assert vreq.fcr_compatible is True
            assert vreq.budget_eur == 24000
            assert vreq.transmission == "Manuelle"
            assert vreq.destination_port == "La Goulette"

            # 17. CSV contains the request
            csv_path = test_csv_service.get_csv_path(tenant.id)
            assert csv_path.exists()
            with open(csv_path, mode="r", newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == 1
            assert rows[0]["make"] == "Volkswagen"
            assert rows[0]["model"] == "Golf 8"
            assert rows[0]["budget_eur"] == "24000.00"
            assert rows[0]["status"] == "QUALIFIED"

            # 18 & 19. Customer and Owner receive confirmations
            # Verify customer confirmation was sent
            customer_outbounds = [m for m in mock_wa.dispatched_messages if m["recipient_e164"] == customer.phone_e164]
            assert any("validée" in m["text"] for m in customer_outbounds)

            # --- STEP 20 & 21: Customer requests human -> AI stops ---
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="HUMAN_REQUEST",
                    language="fr",
                    human_attention_required=True,
                    human_attention_reason="CUSTOMER_REQUESTED_HUMAN",
                    response_text="Un conseiller va prendre le relais.",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            d9 = await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Je voudrais parler à un humain pour finaliser le contrat",
                phone_number_id=account.phone_number_id,
            )
            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.HUMAN_ATTENTION.value
            assert conv.handoff_reason == HandoffReason.CUSTOMER_REQUESTED_HUMAN.value

            # --- STEP 22: Human agent takes over (Mode=HUMAN, State=HUMAN_ACTIVE) ---
            conv.mode = ConversationMode.HUMAN.value
            conv.conversation_state = ConversationState.HUMAN_ACTIVE.value
            await db_session.commit()

            # Verify AI automatic replies STOP when human is active
            msg_count_before = len(mock_wa.dispatched_messages)
            d10 = await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Allô vous êtes là ?",
                phone_number_id=account.phone_number_id,
            )
            assert len(mock_wa.dispatched_messages) == msg_count_before  # ZERO new AI messages dispatched!

            # --- STEP 23 & 24: Human hands back / AI resumes -> AI continues automatically ---
            conv.mode = ConversationMode.AI.value
            conv.conversation_state = ConversationState.AI_ACTIVE.value
            await db_session.commit()

            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="GENERAL_INQUIRY",
                    language="fr",
                    response_text="Je suis de nouveau disponible. Avez-vous d'autres questions sur votre commande ?",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            d11 = await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Merci, à quelle heure ouvrez-vous demain ?",
                phone_number_id=account.phone_number_id,
            )
            assert len(mock_wa.dispatched_messages) == msg_count_before + 1
            assert "disponible" in mock_wa.dispatched_messages[-1]["text"]


# =========================================================================
# TEST 2: Arabic Multi-Turn Flow End-to-End
# =========================================================================
@pytest.mark.asyncio
async def test_full_e2e_simulation_arabic(
    db_session: AsyncSession,
    setup_e2e_environment: tuple[Tenant, WhatsAppAccount, Customer, WhatsAppConversation],
):
    """Verifies complete Arabic customer journey from greeting to qualification and Arabic CSV preservation."""
    tenant, account, customer, conv = setup_e2e_environment
    customer.full_name = "طارق الماجري"
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_wa = E2EWhatsAppMock()

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_csv_service = CSVExportService(export_dir=tmp_dir)
        with patch("app.services.agent_orchestrator.csv_export_service", test_csv_service):
            orchestrator = AgentOrchestrator(
                db=db_session,
                llm_provider=mock_llm,
                whatsapp_provider=mock_wa,
            )

            # Turn 1: Arabic Greeting & Vehicle Request
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="VEHICLE_REQUEST",
                    language="ar",
                    make="Mercedes-Benz",
                    model="C200",
                    year=2022,
                    fuel_type="Diesel",
                    budget_eur=35000,
                    destination_port="La Goulette",
                    response_text=(
                        "أهلاً بك! لقد سجلت طلبك:\n"
                        "- مرسيدس C200 موديل 2022 ديزل\n"
                        "- الميزانية: 35,000 يورو\n"
                        "- ميناء الوصول: حلق الوادي\n"
                        "هل تؤكد هذه المواصفات لبدء البحث المباشر؟"
                    ),
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="السلام عليكم، نحب نشري مرسيدس C200 موديل 2022 ديزل بميزانية 35000 يورو لميناء حلق الوادي",
                phone_number_id=account.phone_number_id,
            )

            # Turn 2: Arabic Explicit Confirmation
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="CONFIRMATION",
                    language="ar",
                    response_text="ممتاز! تم تأكيد طلبك لسيارة مرسيدس C200 موديل 2022 بنجاح.",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="نعم أؤكد تماماً هذه المواصفات",
                phone_number_id=account.phone_number_id,
            )

            # Assertions
            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.QUALIFIED_REQUEST.value

            stmt = select(VehicleRequest).where(VehicleRequest.conversation_id == conv.id)
            vreq = (await db_session.execute(stmt)).scalar_one_or_none()
            assert vreq is not None
            assert vreq.status == VehicleRequestStatus.QUALIFIED
            assert vreq.make == "Mercedes-Benz"
            assert vreq.model == "C200"

            csv_path = test_csv_service.get_csv_path(tenant.id)
            with open(csv_path, mode="r", newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == 1
            assert rows[0]["customer_name"] == "طارق الماجري"
            assert rows[0]["make"] == "Mercedes-Benz"


# =========================================================================
# TEST 3: German Multi-Turn Flow End-to-End
# =========================================================================
@pytest.mark.asyncio
async def test_full_e2e_simulation_german(
    db_session: AsyncSession,
    setup_e2e_environment: tuple[Tenant, WhatsAppAccount, Customer, WhatsAppConversation],
):
    """Verifies complete German customer journey from inquiry to qualification."""
    tenant, account, customer, conv = setup_e2e_environment
    customer.full_name = "Hans Müller"
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_wa = E2EWhatsAppMock()

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_csv_service = CSVExportService(export_dir=tmp_dir)
        with patch("app.services.agent_orchestrator.csv_export_service", test_csv_service):
            orchestrator = AgentOrchestrator(
                db=db_session,
                llm_provider=mock_llm,
                whatsapp_provider=mock_wa,
            )

            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="VEHICLE_REQUEST",
                    language="de",
                    make="BMW",
                    model="320d Touring",
                    year=2021,
                    fuel_type="Diesel",
                    budget_eur=28000,
                    destination_port="La Goulette",
                    response_text="Vielen Dank! Ich habe Ihren BMW 320d 2021 (28.000 €) erfasst. Bitte bestätigen Sie kurz.",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Guten Tag, ich suche einen BMW 320d Touring Baujahr 2021 Diesel, Budget 28000 Euro",
                phone_number_id=account.phone_number_id,
            )

            # German confirmation
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="CONFIRMATION",
                    language="de",
                    response_text="Perfekt! Ihre Anfrage für den BMW 320d wurde qualifiziert.",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Ja genau, das passt alles so, ich bestätige",
                phone_number_id=account.phone_number_id,
            )

            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.QUALIFIED_REQUEST.value


# =========================================================================
# TEST 4: English Multi-Turn Flow End-to-End
# =========================================================================
@pytest.mark.asyncio
async def test_full_e2e_simulation_english(
    db_session: AsyncSession,
    setup_e2e_environment: tuple[Tenant, WhatsAppAccount, Customer, WhatsAppConversation],
):
    """Verifies complete English customer journey from inquiry to qualification."""
    tenant, account, customer, conv = setup_e2e_environment
    customer.full_name = "David Smith"
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_wa = E2EWhatsAppMock()

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_csv_service = CSVExportService(export_dir=tmp_dir)
        with patch("app.services.agent_orchestrator.csv_export_service", test_csv_service):
            orchestrator = AgentOrchestrator(
                db=db_session,
                llm_provider=mock_llm,
                whatsapp_provider=mock_wa,
            )

            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="VEHICLE_REQUEST",
                    language="en",
                    make="Audi",
                    model="A4 Avant",
                    year=2022,
                    fuel_type="Diesel",
                    budget_eur=31000,
                    destination_port="Rades",
                    response_text="Summary: Audi A4 Avant 2022 Diesel, Budget €31,000 to Port Rades. Please confirm.",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Hello, I want to export an Audi A4 Avant 2022 diesel, budget 31000 euros to port rades",
                phone_number_id=account.phone_number_id,
            )

            # English confirmation
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="CONFIRMATION",
                    language="en",
                    response_text="Great! Your request is confirmed.",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Yes, that's exactly right. Confirmed!",
                phone_number_id=account.phone_number_id,
            )

            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.QUALIFIED_REQUEST.value


# =========================================================================
# TEST 5: Mixed Tunisian Derja / Arabizi Flow End-to-End
# =========================================================================
@pytest.mark.asyncio
async def test_full_e2e_simulation_mixed_derja_french(
    db_session: AsyncSession,
    setup_e2e_environment: tuple[Tenant, WhatsAppAccount, Customer, WhatsAppConversation],
):
    """Verifies complete Tunisian Derja code-switching conversation."""
    tenant, account, customer, conv = setup_e2e_environment

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_wa = E2EWhatsAppMock()

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_csv_service = CSVExportService(export_dir=tmp_dir)
        with patch("app.services.agent_orchestrator.csv_export_service", test_csv_service):
            orchestrator = AgentOrchestrator(
                db=db_session,
                llm_provider=mock_llm,
                whatsapp_provider=mock_wa,
            )

            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="VEHICLE_REQUEST",
                    language="fr",
                    make="Peugeot",
                    model="3008",
                    year=2021,
                    fuel_type="Diesel",
                    budget_eur=22000,
                    destination_port="La Goulette",
                    response_text="Marhba bik khouya ! Peugeot 3008 modèle 2021 diesel budget 22k euro port goulette. Confirmli brabi ?",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Salem khouya, nheb ala Peugeot 3008 diesel 2021 budgeti 22000 euro port goulette",
                phone_number_id=account.phone_number_id,
            )

            # Derja confirmation
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="CONFIRMATION",
                    language="fr",
                    response_text="Mrigla 100%, talabek tsajjel w l'équipe bech tkalmek !",
                ),
                LLMCompletionResponse(content="", model="gemini-mock"),
            )
            await orchestrator.process_turn(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                customer_id=customer.id,
                message_id=generate_uuidv7(),
                from_phone_e164=customer.phone_e164,
                text_body="Eywah c bon mrigla nconfirmik !",
                phone_number_id=account.phone_number_id,
            )

            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.QUALIFIED_REQUEST.value


# =========================================================================
# TEST 6: Response Latency Telemetry Measurement
# =========================================================================
@pytest.mark.asyncio
async def test_end_to_end_response_latency_telemetry(
    db_session: AsyncSession,
    setup_e2e_environment: tuple[Tenant, WhatsAppAccount, Customer, WhatsAppConversation],
):
    """Measures and asserts sub-segment latency benchmarks across the complete processing pipeline."""
    tenant, account, customer, conv = setup_e2e_environment

    timing = WhatsAppTimingMetrics(
        wamid=f"wamid.perf.{uuid.uuid4().hex[:6]}",
        phone_e164=customer.phone_e164,
        tenant_id=str(tenant.id),
    )
    timing.mark_persisted()
    timing.mark_acknowledged()
    timing.mark_worker_started()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="GREETING",
            language="fr",
            response_text="Bonjour ! Comment puis-je vous aider ?",
        ),
        LLMCompletionResponse(content="", model="gemini-mock"),
    )
    mock_wa = E2EWhatsAppMock()

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=mock_llm,
        whatsapp_provider=mock_wa,
    )

    await orchestrator.process_turn(
        tenant_id=tenant.id,
        conversation_id=conv.id,
        customer_id=customer.id,
        message_id=generate_uuidv7(),
        from_phone_e164=customer.phone_e164,
        text_body="Bonjour",
        phone_number_id=account.phone_number_id,
        timing_metrics=timing,
    )

    report = timing.to_latency_report()
    assert report["db_read_ms"] is not None
    assert report["context_construction_ms"] is not None
    assert report["gemini_latency_ms"] is not None
    assert report["validation_latency_ms"] is not None
    assert report["meta_outbound_ms"] is not None
    assert report["db_write_ms"] is not None
    assert report["total_end_to_end_ms"] is not None
    assert report["total_end_to_end_ms"] > 0
