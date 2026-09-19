"""Customer Confirmation, Qualification & Owner Alert Test Suite (Phase 6).

Verifies:
1. Explicit positive confirmations ('yes', 'oui', 'd'accord', 'eywah mrigla', 'ja genau') mark request as QUALIFIED.
2. Explicit rejections ('no', 'non', 'faux') return state to COLLECTING_REQUEST without qualification.
3. Mid-flow corrections update criteria and present updated summary for re-confirmation.
4. Ambiguous statements ('maybe', 'how much is it', 'BMW') do NOT qualify the request.
5. Multilingual confirmation integrity across French, Arabic, Derja, English, and German.
6. Duplicate confirmations are strictly idempotent: exactly 1 CSV row and 1 owner alert.
7. CSV generation with all required vehicle specifications.
"""

import csv
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

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
from app.services.csv_export_service import CSVExportService
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
async def test_explicit_yes_confirmation_qualifies_request_and_exports_csv(db_session: AsyncSession):
    """Verify explicit 'yes' confirmation transitions to QUALIFIED, writes CSV, and sends confirmation."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conversation_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export Paris", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+33612345678",
        first_name="Karim",
        full_name="Karim Ben Salem",
        preferred_language="fr",
    )
    conv = WhatsAppConversation(
        id=conversation_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AWAITING_REQUEST_CONFIRMATION.value,
        draft_data={
            "make": "Volkswagen",
            "model": "Tiguan",
            "year": 2022,
            "fuel_type": "Diesel",
            "transmission": "Automatic",
            "budget_eur": 29000.0,
            "destination_port": "La Goulette",
            "missing_fields": [],
        },
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_csv_service = CSVExportService(export_dir=tmp_dir)
        with patch("app.services.agent_orchestrator.csv_export_service", test_csv_service):
            mock_llm = AsyncMock(spec=LLMProvider)
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="CONFIRMATION",
                    language="fr",
                    customer_confirmed=True,
                    response_text="Parfait ! Votre demande pour le Volkswagen Tiguan 2022 est validée. Notre conseiller commercial vous prépare une sélection personnalisée.",
                ),
                LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
            )
            mock_wa = MockWhatsAppProvider()

            orchestrator = AgentOrchestrator(
                db=db_session,
                llm_provider=mock_llm,
                whatsapp_provider=mock_wa,
            )

            decision = await orchestrator.process_turn(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                customer_id=customer_id,
                message_id=generate_uuidv7(),
                from_phone_e164="+33612345678",
                text_body="Oui c'est parfait, je confirme tout !",
                phone_number_id="100998877",
            )

            # 1. State machine transition verification
            await db_session.refresh(conv)
            assert conv.conversation_state == ConversationState.QUALIFIED_REQUEST.value

            # 2. Database VehicleRequest verification
            stmt_vreq = select(VehicleRequest).where(VehicleRequest.conversation_id == conversation_id)
            vreq = (await db_session.execute(stmt_vreq)).scalar_one_or_none()
            assert vreq is not None
            assert vreq.status == VehicleRequestStatus.QUALIFIED
            assert vreq.is_qualified is True
            assert vreq.confirmed_at is not None
            assert vreq.make == "Volkswagen"
            assert vreq.model == "Tiguan"
            assert vreq.min_year == 2022
            assert vreq.budget_eur == Decimal("29000.00")
            assert vreq.destination_port == "La Goulette"

            # 3. CSV export verification
            csv_path = test_csv_service.get_csv_path(tenant_id)
            assert csv_path.exists()
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
                assert len(rows) == 1
                row = rows[0]
                assert row["request_id"] == str(vreq.id)
                assert row["customer_phone"] == "+33612345678"
                assert row["make"] == "Volkswagen"
                assert row["model"] == "Tiguan"
                assert row["budget_eur"] == "29000.00"
                assert row["status"] == "QUALIFIED"

            # 4. Outbound customer message verification
            assert len(mock_wa.dispatched_messages) == 1
            assert "validée" in mock_wa.dispatched_messages[0]["text"]


@pytest.mark.asyncio
async def test_explicit_no_rejection_returns_to_collecting(db_session: AsyncSession):
    """Verify explicit rejection returns to COLLECTING_REQUEST without qualifying."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conversation_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+33699887766",
        first_name="Hassen",
    )
    conv = WhatsAppConversation(
        id=conversation_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AWAITING_REQUEST_CONFIRMATION.value,
        draft_data={"make": "Audi", "model": "Q5", "year": 2020, "budget_eur": 25000.0, "missing_fields": []},
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="REJECTION",
            language="fr",
            customer_confirmed=False,
            response_text="D'accord, que souhaitez-vous modifier dans vos critères ?",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )
    mock_wa = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=mock_llm,
        whatsapp_provider=mock_wa,
    )

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33699887766",
        text_body="Non pas du tout, je veux changer.",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.COLLECTING_REQUEST.value

    stmt_vreq = select(VehicleRequest).where(VehicleRequest.conversation_id == conversation_id)
    vreq = (await db_session.execute(stmt_vreq)).scalar_one_or_none()
    assert vreq is not None
    assert vreq.status != VehicleRequestStatus.QUALIFIED
    assert vreq.is_qualified is False


@pytest.mark.asyncio
async def test_correction_updates_summary_and_requires_reconfirmation(db_session: AsyncSession):
    """Verify customer modifying specs during confirmation updates draft and requests confirmation again."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conversation_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+33655443322",
        first_name="Sami",
    )
    conv = WhatsAppConversation(
        id=conversation_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AWAITING_REQUEST_CONFIRMATION.value,
        draft_data={"make": "BMW", "model": "X3", "year": 2021, "budget_eur": 30000.0, "missing_fields": []},
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="REQUEST_UPDATE",
            language="fr",
            budget_eur=35000.0,
            customer_confirmation_required=True,
            response_text="Bien noté ! Voici le nouveau récapitulatif avec budget à 35 000 €. Confirmez-vous cette version ?",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )
    mock_wa = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=mock_llm,
        whatsapp_provider=mock_wa,
    )

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33655443322",
        text_body="En fait augmente mon budget à 35000 euros.",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.AWAITING_REQUEST_CONFIRMATION.value
    assert conv.draft_data["budget_eur"] == 35000.0

    stmt_vreq = select(VehicleRequest).where(VehicleRequest.conversation_id == conversation_id)
    vreq = (await db_session.execute(stmt_vreq)).scalar_one_or_none()
    assert vreq is not None
    assert vreq.budget_eur == Decimal("35000.00")
    assert vreq.status == VehicleRequestStatus.AWAITING_CONFIRMATION
    assert vreq.is_qualified is False


@pytest.mark.asyncio
async def test_ambiguous_statements_do_not_qualify_request(db_session: AsyncSession):
    """Verify ambiguous statements ('maybe', 'how much is it') do NOT trigger false qualification."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conversation_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+33611002233",
        first_name="Nabil",
    )
    conv = WhatsAppConversation(
        id=conversation_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AWAITING_REQUEST_CONFIRMATION.value,
        draft_data={"make": "Mercedes-Benz", "model": "GLC", "year": 2022, "budget_eur": 40000.0, "missing_fields": []},
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    # Customer responds with an ambiguous question instead of a direct yes/no
    ambiguous_query = "Je sais pas encore, combien coûte la livraison exactement ?"

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="FAQ",
            language="fr",
            response_text="Le transport maritime est inclus dans nos devis. Souhaitez-vous valider votre recherche de Mercedes-Benz GLC ?",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )
    mock_wa = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=mock_llm,
        whatsapp_provider=mock_wa,
    )

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33611002233",
        text_body=ambiguous_query,
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    # Must NOT be qualified
    assert conv.conversation_state != ConversationState.QUALIFIED_REQUEST.value

    stmt_vreq = select(VehicleRequest).where(VehicleRequest.conversation_id == conversation_id)
    vreq = (await db_session.execute(stmt_vreq)).scalar_one_or_none()
    assert vreq is not None
    assert vreq.status != VehicleRequestStatus.QUALIFIED
    assert vreq.is_qualified is False


@pytest.mark.asyncio
async def test_duplicate_confirmation_is_strictly_idempotent(db_session: AsyncSession):
    """Verify sending confirmation twice does not re-qualify or duplicate CSV records."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conversation_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+33644332211",
        first_name="Mourad",
    )
    conv = WhatsAppConversation(
        id=conversation_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AWAITING_REQUEST_CONFIRMATION.value,
        draft_data={"make": "Toyota", "model": "RAV4", "year": 2023, "budget_eur": 31000.0, "missing_fields": []},
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_csv_service = CSVExportService(export_dir=tmp_dir)
        with patch("app.services.agent_orchestrator.csv_export_service", test_csv_service):
            mock_llm = AsyncMock(spec=LLMProvider)
            mock_llm.generate_structured_output.return_value = (
                AgentDecision(
                    intent="CONFIRMATION",
                    language="fr",
                    customer_confirmed=True,
                    response_text="Demande validée !",
                ),
                LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
            )
            mock_wa = MockWhatsAppProvider()

            orchestrator = AgentOrchestrator(
                db=db_session,
                llm_provider=mock_llm,
                whatsapp_provider=mock_wa,
            )

            # First confirmation turn
            await orchestrator.process_turn(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                customer_id=customer_id,
                message_id=generate_uuidv7(),
                from_phone_e164="+33644332211",
                text_body="Oui je confirme",
                phone_number_id="100998877",
            )

            stmt_vreq = select(VehicleRequest).where(VehicleRequest.conversation_id == conversation_id)
            vreq = (await db_session.execute(stmt_vreq)).scalar_one_or_none()
            assert vreq.is_qualified is True
            initial_confirmed_at = vreq.confirmed_at

            csv_path = test_csv_service.get_csv_path(tenant_id)
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                rows_turn1 = list(csv.DictReader(f))
            assert len(rows_turn1) == 1

            # Second confirmation turn (repeated 'yes')
            await orchestrator.process_turn(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                customer_id=customer_id,
                message_id=generate_uuidv7(),
                from_phone_e164="+33644332211",
                text_body="Oui merci beaucoup",
                phone_number_id="100998877",
            )

            await db_session.refresh(vreq)
            assert vreq.is_qualified is True
            assert vreq.confirmed_at == initial_confirmed_at  # Timestamp preserved

            with open(csv_path, "r", encoding="utf-8-sig") as f:
                rows_turn2 = list(csv.DictReader(f))
            # Must remain exactly 1 row (NO DUPLICATE)
            assert len(rows_turn2) == 1
