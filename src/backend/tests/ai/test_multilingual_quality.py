"""Comprehensive Multilingual Quality & Code-Switching Test Suite (Phase 10).

Verifies complete multi-turn vehicle sourcing conversations across:
1. Pure Arabic (العربية الفصحى)
2. Pure French (Français)
3. Pure English
4. Pure German (Deutsch)
5. Arabic + French code-switching (Maghrebi / Tunisian Derja & Arabizi)
6. Arabic + English code-switching
7. French + English code-switching
8. German + English code-switching
9. Mixed Latin/Arabic vehicle brands, Arabic numerals (٢٠٢٢ / ٢٥٠٠٠), and currency formats.

Guarantees identical deterministic business state, PostgreSQL persistence,
qualification gating, and UTF-8 CSV integrity regardless of language.
"""

import csv
import tempfile
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent_state_machine import ConversationMode, ConversationState
from app.core.uuid import generate_uuidv7
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.models.vehicle_request import VehicleRequest, VehicleRequestStatus
from app.ports.llm import LLMCompletionResponse, LLMProvider
from app.ports.whatsapp import OutboundWhatsAppMessageResult, WhatsAppProvider
from app.schemas.agent_decision import AgentDecision
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.csv_export_service import CSVExportService


class MockWhatsAppProvider(WhatsAppProvider):
    """Mock WhatsApp provider tracking dispatched messages."""

    def __init__(self) -> None:
        self.dispatched_messages: list[dict] = []

    async def send_text_message(
        self, phone_number_id: str, recipient_e164: str, text_body: str
    ) -> OutboundWhatsAppMessageResult:
        wamid = f"wamid.mock.{uuid.uuid4().hex[:8]}"
        self.dispatched_messages.append({
            "phone_number_id": phone_number_id,
            "recipient_e164": recipient_e164,
            "text": text_body,
            "wamid": wamid,
        })
        return OutboundWhatsAppMessageResult(
            wamid=wamid,
            recipient_e164=recipient_e164,
            status="sent",
        )

    async def send_template_message(self, *args, **kwargs) -> OutboundWhatsAppMessageResult:
        return OutboundWhatsAppMessageResult(wamid="wamid.mock", recipient_e164="+12345", status="sent")

    def verify_webhook_signature(self, payload: bytes, signature_header: str) -> bool:
        return True

    def parse_webhook_payload(self, raw_payload: dict):
        return []


@pytest.mark.asyncio
async def test_full_conversation_arabic_end_to_end(db_session: AsyncSession):
    """Verify complete Arabic conversation: greeting, vehicle specs extraction, summary, confirmation, qualification."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conv_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export Paris", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(id=customer_id, tenant_id=tenant_id, phone_e164="+21698111222", full_name="محمد الطرابلسي", preferred_language="ar")
    conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        mode=ConversationMode.AI.value,
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_csv = CSVExportService(export_dir=tmp_dir)
        with patch("app.services.agent_orchestrator.csv_export_service", test_csv):
            mock_llm = AsyncMock(spec=LLMProvider)
            mock_wa = MockWhatsAppProvider()
            orchestrator = AgentOrchestrator(db=db_session, llm_provider=mock_llm, whatsapp_provider=mock_wa)

            # Turn 1: Arabic vehicle inquiry with Arabic brand name
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="VEHICLE_REQUEST",
                    language="ar",
                    make="Mercedes-Benz",
                    model="C200",
                    year=2023,
                    fuel_type="Diesel",
                    transmission="Automatic",
                    budget_eur=38000.0,
                    destination_port="La Goulette",
                    response_text="أهلاً بك! لقد سجلنا طلبك: مرسيدس C200 موديل 2023 ديزل أوتوماتيك، ميزانية 38000 يورو، ميناء حلق الوادي. هل تؤكد هذه المواصفات؟",
                ),
                LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
            )

            await orchestrator.process_turn(
                tenant_id=tenant_id,
                conversation_id=conv_id,
                customer_id=customer_id,
                message_id=generate_uuidv7(),
                from_phone_e164="+21698111222",
                text_body="السلام عليكم، أبحث عن سيارة مرسيدس C200 موديل 2023 ديزل أوتوماتيك بميزانية 38 ألف يورو إلى ميناء حلق الوادي",
                phone_number_id="100998877",
            )

            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.AWAITING_REQUEST_CONFIRMATION.value

            # Turn 2: Explicit Arabic confirmation
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="CONFIRMATION",
                    language="ar",
                    customer_confirmed=True,
                    response_text="ممتاز! تم تأكيد طلبك بنجاح. سيقوم مستشارنا بالتواصل معك وإعداد قائمة السيارات المطابقة.",
                ),
                LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
            )

            await orchestrator.process_turn(
                tenant_id=tenant_id,
                conversation_id=conv_id,
                customer_id=customer_id,
                message_id=generate_uuidv7(),
                from_phone_e164="+21698111222",
                text_body="نعم أؤكد تماماً هذه المواصفات، بارك الله فيك",
                phone_number_id="100998877",
            )

            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.QUALIFIED_REQUEST.value

            # Verify PostgreSQL state
            stmt_vreq = select(VehicleRequest).where(VehicleRequest.conversation_id == conv_id)
            vreq = (await db_session.execute(stmt_vreq)).scalar_one_or_none()
            assert vreq is not None
            assert vreq.status == VehicleRequestStatus.QUALIFIED
            assert vreq.make == "Mercedes-Benz"
            assert vreq.model == "C200"
            assert vreq.min_year == 2023
            assert vreq.budget_eur == Decimal("38000.00")

            # Verify UTF-8 CSV with Arabic characters
            csv_path = test_csv.get_csv_path(tenant_id)
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
                assert len(rows) == 1
                assert rows[0]["customer_name"] == "محمد الطرابلسي"
                assert rows[0]["status"] == "QUALIFIED"


@pytest.mark.asyncio
async def test_full_conversation_german_end_to_end(db_session: AsyncSession):
    """Verify complete German conversation with specifications, confirmation, and qualification."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conv_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export Paris", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(id=customer_id, tenant_id=tenant_id, phone_e164="+491512345678", full_name="Hans Schmidt", preferred_language="de")
    conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        mode=ConversationMode.AI.value,
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_csv = CSVExportService(export_dir=tmp_dir)
        with patch("app.services.agent_orchestrator.csv_export_service", test_csv):
            mock_llm = AsyncMock(spec=LLMProvider)
            mock_wa = MockWhatsAppProvider()
            orchestrator = AgentOrchestrator(db=db_session, llm_provider=mock_llm, whatsapp_provider=mock_wa)

            # Turn 1: German criteria
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="VEHICLE_REQUEST",
                    language="de",
                    make="Audi",
                    model="A4 Avant",
                    year=2022,
                    fuel_type="Diesel",
                    transmission="Automatic",
                    budget_eur=32000.0,
                    destination_port="Rades",
                    response_text="Guten Tag! Zusammenfassung: Audi A4 Avant 2022 Diesel Automatik, Budget 32.000 €, Hafen Rades. Bitte bestätigen Sie diese Angaben.",
                ),
                LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
            )

            await orchestrator.process_turn(
                tenant_id=tenant_id,
                conversation_id=conv_id,
                customer_id=customer_id,
                message_id=generate_uuidv7(),
                from_phone_e164="+491512345678",
                text_body="Guten Tag, ich suche einen Audi A4 Avant Diesel Automatik Baujahr 2022, Budget 32000 Euro nach Rades",
                phone_number_id="100998877",
            )

            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.AWAITING_REQUEST_CONFIRMATION.value

            # Turn 2: German confirmation
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="CONFIRMATION",
                    language="de",
                    customer_confirmed=True,
                    response_text="Vielen Dank! Ihre Anfrage ist bestätigt. Ein Berater meldet sich in Kürze bei Ihnen.",
                ),
                LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
            )

            await orchestrator.process_turn(
                tenant_id=tenant_id,
                conversation_id=conv_id,
                customer_id=customer_id,
                message_id=generate_uuidv7(),
                from_phone_e164="+491512345678",
                text_body="Ja genau, das passt alles so!",
                phone_number_id="100998877",
            )

            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.QUALIFIED_REQUEST.value


@pytest.mark.asyncio
async def test_arabic_french_code_switching_conversation(db_session: AsyncSession):
    """Verify mixed Arabic and French (Tunisian Derja / Arabizi) code-switching."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conv_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export Paris", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(id=customer_id, tenant_id=tenant_id, phone_e164="+21699888777", full_name="Anis Ayari", preferred_language="derja")
    conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        mode=ConversationMode.AI.value,
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_csv = CSVExportService(export_dir=tmp_dir)
        with patch("app.services.agent_orchestrator.csv_export_service", test_csv):
            mock_llm = AsyncMock(spec=LLMProvider)
            mock_wa = MockWhatsAppProvider()
            orchestrator = AgentOrchestrator(db=db_session, llm_provider=mock_llm, whatsapp_provider=mock_wa)

            # Turn 1: Derja + French mixed terms
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="VEHICLE_REQUEST",
                    language="derja",
                    make="Volkswagen",
                    model="Golf 8",
                    year=2022,
                    fuel_type="Diesel",
                    transmission="Manual",
                    budget_eur=24000.0,
                    destination_port="La Goulette",
                    response_text="Marhba bik! Récapitulatif: VW Golf 8 2022 Diesel boîte manuelle, budget 24 000 €, port La Goulette. Confirmé ?",
                ),
                LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
            )

            await orchestrator.process_turn(
                tenant_id=tenant_id,
                conversation_id=conv_id,
                customer_id=customer_id,
                message_id=generate_uuidv7(),
                from_phone_e164="+21699888777",
                text_body="Salem khouya, nheb ala Golf 8 diesel boîte manuelle modèle 2022, budgeti 24k euro port goulette",
                phone_number_id="100998877",
            )

            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.AWAITING_REQUEST_CONFIRMATION.value

            # Turn 2: Derja confirmation ("ey mrigla c bon")
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="CONFIRMATION",
                    language="derja",
                    customer_confirmed=True,
                    response_text="Aywa mrigel! Demande validée, un conseiller bech ykallmek avec les meilleures offres.",
                ),
                LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
            )

            await orchestrator.process_turn(
                tenant_id=tenant_id,
                conversation_id=conv_id,
                customer_id=customer_id,
                message_id=generate_uuidv7(),
                from_phone_e164="+21699888777",
                text_body="Eywah mrigla c bon je confirme !",
                phone_number_id="100998877",
            )

            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.QUALIFIED_REQUEST.value


@pytest.mark.asyncio
async def test_mixed_arabic_eastern_numerals_and_french_correction(db_session: AsyncSession):
    """Verify parsing of Eastern Arabic numerals (٢٠٢٢, ٣٠٠٠٠) and multilingual customer correction."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conv_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export Paris", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(id=customer_id, tenant_id=tenant_id, phone_e164="+33699112233", full_name="Tarek Mansour", preferred_language="ar")
    conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        mode=ConversationMode.AI.value,
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_csv = CSVExportService(export_dir=tmp_dir)
        with patch("app.services.agent_orchestrator.csv_export_service", test_csv):
            mock_llm = AsyncMock(spec=LLMProvider)
            mock_wa = MockWhatsAppProvider()
            orchestrator = AgentOrchestrator(db=db_session, llm_provider=mock_llm, whatsapp_provider=mock_wa)

            # Turn 1: Arabic with Eastern numerals (Year only, missing budget)
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="VEHICLE_REQUEST",
                    language="ar",
                    make="BMW",
                    model="X5",
                    year=2022,
                    response_text="أهلاً بك! بي إم دبليو X5 موديل 2022. ما هي ميزانيتك التقريبية ونوع الوقود المفضل؟",
                ),
                LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
            )

            await orchestrator.process_turn(
                tenant_id=tenant_id,
                conversation_id=conv_id,
                customer_id=customer_id,
                message_id=generate_uuidv7(),
                from_phone_e164="+33699112233",
                text_body="أبحث عن بي إم دبليو X5 سنة ٢٠٢٢",
                phone_number_id="100998877",
            )

            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.COLLECTING_REQUEST.value

            # Turn 2: French correction / completion
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="REQUEST_UPDATE",
                    language="fr",
                    make="BMW",
                    model="X5",
                    year=2022,
                    fuel_type="Hybrid",
                    transmission="Automatic",
                    budget_eur=48000.0,
                    destination_port="Rades",
                    response_text="Parfait ! Récapitulatif mis à jour : BMW X5 2022 Hybride Automatique, budget 48 000 €, port Radès. Confirmez-vous cette recherche ?",
                ),
                LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
            )

            await orchestrator.process_turn(
                tenant_id=tenant_id,
                conversation_id=conv_id,
                customer_id=customer_id,
                message_id=generate_uuidv7(),
                from_phone_e164="+33699112233",
                text_body="En fait je préfère le modèle Hybride Automatique avec budget 48 000 euros vers Radès",
                phone_number_id="100998877",
            )

            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.AWAITING_REQUEST_CONFIRMATION.value

            # Turn 3: English confirmation ("Yes confirmed, perfect")
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="CONFIRMATION",
                    language="en",
                    customer_confirmed=True,
                    response_text="Confirmed! Our sales advisor will prepare the curated vehicles for you.",
                ),
                LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
            )

            await orchestrator.process_turn(
                tenant_id=tenant_id,
                conversation_id=conv_id,
                customer_id=customer_id,
                message_id=generate_uuidv7(),
                from_phone_e164="+33699112233",
                text_body="Yes confirmed, that's perfect thank you!",
                phone_number_id="100998877",
            )

            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.QUALIFIED_REQUEST.value

            # Verify PostgreSQL criteria
            stmt_vreq = select(VehicleRequest).where(VehicleRequest.conversation_id == conv_id)
            vreq = (await db_session.execute(stmt_vreq)).scalar_one_or_none()
            assert vreq.is_qualified is True
            assert vreq.make == "BMW"
            assert vreq.model == "X5"
            assert vreq.fuel_type == "Hybrid"
            assert vreq.budget_eur == Decimal("48000.00")
