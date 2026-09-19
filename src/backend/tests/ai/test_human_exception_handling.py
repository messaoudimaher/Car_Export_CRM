"""Tests for Phase 8: Human Exception Handling, Takeover, and AI Resume Lifecycle.

Verifies:
1. Customer asking for human triggers HUMAN_ATTENTION (Multilingual).
2. Unsupported/unknown company facts trigger HUMAN_ATTENTION (UNSUPPORTED_QUESTION).
3. Customer complaints trigger HUMAN_ATTENTION (COMPLAINT).
4. Business decisions / price negotiations trigger HUMAN_ATTENTION (PRICE_REQUEST).
5. Unresolved ambiguity triggers HUMAN_ATTENTION (AMBIGUOUS_REQUEST).
6. Technical failures trigger graceful fallback to HUMAN_ATTENTION (TECHNICAL_ERROR).
7. HUMAN_ACTIVE halts automatic AI responses completely.
8. Resuming AI re-enables automatic responses.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent_state_machine import ConversationMode, ConversationState, HandoffReason
from app.core.uuid import generate_uuidv7
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.ports.llm import LLMCompletionResponse, LLMProvider
from app.ports.whatsapp import OutboundWhatsAppMessageResult, WhatsAppProvider
from app.schemas.agent_decision import AgentDecision
from app.services.agent_orchestrator import AgentOrchestrator


class MockWhatsAppProvider(WhatsAppProvider):
    """Mock WhatsApp provider tracking outbound messages."""

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
@pytest.mark.parametrize(
    "phrase,lang",
    [
        ("Je voudrais parler à un conseiller humain s'il vous plaît", "fr"),
        ("I need to speak to a real human agent please", "en"),
        ("أريد التحدث مع موظف خدمة العملاء", "ar"),
        ("kallamni rajil wehed yefhem fel export", "derja"),
        ("Ich möchte mit einem menschlichen Berater sprechen", "de"),
    ],
)
async def test_customer_asking_for_human_triggers_human_attention(
    db_session: AsyncSession, phrase: str, lang: str
):
    """Verify customer explicitly requesting a human agent transitions state to HUMAN_ATTENTION."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conv_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export Paris", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(id=customer_id, tenant_id=tenant_id, phone_e164="+33611223344", full_name="Sami Trabelsi")
    conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        mode=ConversationMode.AI.value,
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="HUMAN_REQUEST",
            language=lang,
            human_attention_required=True,
            human_attention_reason="CUSTOMER_REQUESTED_HUMAN",
            response_text="Bien sûr, je transmets immédiatement votre dossier à l'un de nos conseillers commerciaux.",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )
    mock_wa = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(db=db_session, llm_provider=mock_llm, whatsapp_provider=mock_wa)

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conv_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33611223344",
        text_body=phrase,
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.HUMAN_ATTENTION.value
    assert conv.handoff_reason == HandoffReason.CUSTOMER_REQUESTED_HUMAN.value
    assert len(mock_wa.dispatched_messages) >= 1


@pytest.mark.asyncio
async def test_customer_complaint_triggers_human_attention(db_session: AsyncSession):
    """Verify customer complaint or dispute escalates to HUMAN_ATTENTION with COMPLAINT reason."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conv_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export Paris", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(id=customer_id, tenant_id=tenant_id, phone_e164="+33622334455", full_name="Ali Mahmoud")
    conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        mode=ConversationMode.AI.value,
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="COMPLAINT",
            language="fr",
            human_attention_required=True,
            human_attention_reason="COMPLAINT",
            response_text="Nous sommes navrés d'apprendre votre mécontentement. Un responsable de notre direction va vous recontacter directement.",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )
    mock_wa = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(db=db_session, llm_provider=mock_llm, whatsapp_provider=mock_wa)

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conv_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33622334455",
        text_body="C'est inadmissible, vous êtes des voleurs ! Je veux déposer une plainte pour mauvais service.",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.HUMAN_ATTENTION.value
    assert conv.handoff_reason == HandoffReason.COMPLAINT.value


@pytest.mark.asyncio
async def test_unsupported_company_inquiry_triggers_human_attention(db_session: AsyncSession):
    """Verify out-of-scope company policy inquiry triggers HUMAN_ATTENTION without hallucinating facts."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conv_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export Paris", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(id=customer_id, tenant_id=tenant_id, phone_e164="+33633445566", full_name="Youssef Gharbi")
    conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        mode=ConversationMode.AI.value,
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="FAQ",
            language="fr",
            human_attention_required=True,
            human_attention_reason="UNSUPPORTED_QUESTION",
            response_text="Nous n'avons pas d'agence à Dubaï. Notre conseiller va vérifier avec vous les possibilités d'exportation vers la Tunisie.",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )
    mock_wa = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(db=db_session, llm_provider=mock_llm, whatsapp_provider=mock_wa)

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conv_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33633445566",
        text_body="Puis-je visiter votre agence physique à Dubaï et payer en crypto-monnaie Bitcoin ?",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.HUMAN_ATTENTION.value
    assert conv.handoff_reason == HandoffReason.UNSUPPORTED_QUESTION.value


@pytest.mark.asyncio
async def test_price_discount_negotiation_triggers_human_attention(db_session: AsyncSession):
    """Verify binding price discount demand escalates to human advisor."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conv_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export Paris", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(id=customer_id, tenant_id=tenant_id, phone_e164="+33655667788", full_name="Mourad Khelifi")
    conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.COLLECTING_REQUEST.value,
        mode=ConversationMode.AI.value,
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="PRICE_REQUEST",
            language="fr",
            human_attention_required=True,
            human_attention_reason="PRICE_REQUEST",
            response_text="Pour toute négociation de remise commerciale ou devis officiel ferme, un conseiller commercial va vous contacter directement.",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )
    mock_wa = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(db=db_session, llm_provider=mock_llm, whatsapp_provider=mock_wa)

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conv_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33655667788",
        text_body="Je veux négocier une remise ferme sur le devis final avant de signer.",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.HUMAN_ATTENTION.value
    assert conv.handoff_reason == HandoffReason.PRICE_REQUEST.value


@pytest.mark.asyncio
async def test_technical_failure_falls_back_gracefully_to_human_attention(db_session: AsyncSession):
    """Verify LLM outage or technical error does not crash and escalates safely to HUMAN_ATTENTION."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conv_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export Paris", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(id=customer_id, tenant_id=tenant_id, phone_e164="+33677889900", full_name="Fatma Ben Amor")
    conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        mode=ConversationMode.AI.value,
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    # Simulate Gemini API outage
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.side_effect = RuntimeError("Gemini API 503 Service Unavailable")
    mock_wa = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(db=db_session, llm_provider=mock_llm, whatsapp_provider=mock_wa)

    decision = await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conv_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33677889900",
        text_body="Bonjour je cherche une voiture",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.HUMAN_ATTENTION.value
    assert conv.handoff_reason == HandoffReason.TECHNICAL_ERROR.value
    assert len(mock_wa.dispatched_messages) == 1
    assert "incident technique" in mock_wa.dispatched_messages[0]["text"]


@pytest.mark.asyncio
async def test_human_active_mode_completely_halts_ai_replies(db_session: AsyncSession):
    """Verify that when mode == HUMAN or state == HUMAN_ACTIVE, AI auto-replies MUST STOP."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conv_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export Paris", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(id=customer_id, tenant_id=tenant_id, phone_e164="+33699887766", full_name="Hassen Riahi")
    conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.HUMAN_ACTIVE.value,
        mode=ConversationMode.HUMAN.value,
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_wa = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(db=db_session, llm_provider=mock_llm, whatsapp_provider=mock_wa)

    decision = await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conv_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33699887766",
        text_body="Bonjour, avez-vous reçu mes documents ?",
        phone_number_id="100998877",
    )

    # 1. LLM must NEVER be called
    mock_llm.generate_structured_output.assert_not_called()

    # 2. Outbound WhatsApp message must NEVER be sent
    assert len(mock_wa.dispatched_messages) == 0

    # 3. Decision must reflect skipped turn
    assert decision.intent == "HUMAN_REQUEST"


@pytest.mark.asyncio
async def test_resuming_ai_reenables_automatic_replies(db_session: AsyncSession):
    """Verify that resuming AI from HUMAN mode re-enables automatic replies on subsequent messages."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conv_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export Paris", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(id=customer_id, tenant_id=tenant_id, phone_e164="+33612344321", full_name="Zied Mansour")
    conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.HUMAN_ACTIVE.value,
        mode=ConversationMode.HUMAN.value,
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="VEHICLE_REQUEST",
            language="fr",
            make="Peugeot",
            model="3008",
            response_text="Très bon choix ! Quelle année et quelle motorisation préférez-vous pour le Peugeot 3008 ?",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )
    mock_wa = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(db=db_session, llm_provider=mock_llm, whatsapp_provider=mock_wa)

    # 1. While in HUMAN mode, message is ignored by AI
    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conv_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33612344321",
        text_body="Je cherche un Peugeot 3008",
        phone_number_id="100998877",
    )
    assert len(mock_wa.dispatched_messages) == 0

    # 2. Human operator resumes AI (mode -> AI, conversation_state -> AI_ACTIVE)
    conv.mode = ConversationMode.AI.value
    conv.conversation_state = ConversationState.AI_ACTIVE.value
    conv.handoff_reason = None
    conv.handoff_summary = None
    await db_session.commit()

    # 3. Next customer message triggers AI autonomous reply normally
    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conv_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33612344321",
        text_body="Je cherche un Peugeot 3008",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.COLLECTING_REQUEST.value
    assert len(mock_wa.dispatched_messages) == 1
    assert "Peugeot 3008" in mock_wa.dispatched_messages[0]["text"]


@pytest.mark.asyncio
async def test_unresolved_ambiguity_triggers_human_attention(db_session: AsyncSession):
    """Verify incomprehensible or low-confidence ambiguous messages escalate to HUMAN_ATTENTION."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conv_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export Paris", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(id=customer_id, tenant_id=tenant_id, phone_e164="+33688990011", full_name="Karim Dridi")
    conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        mode=ConversationMode.AI.value,
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="OTHER",
            language="fr",
            confidence=0.2,
            human_attention_required=True,
            human_attention_reason="AMBIGUOUS_REQUEST",
            response_text="Je ne suis pas certain de bien comprendre votre demande. Un conseiller va vous assister directement.",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )
    mock_wa = MockWhatsAppProvider()

    orchestrator = AgentOrchestrator(db=db_session, llm_provider=mock_llm, whatsapp_provider=mock_wa)

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conv_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33688990011",
        text_body="xyz qwerty asdfgh jkl",
        phone_number_id="100998877",
    )

    await db_session.refresh(conv)
    assert conv.conversation_state == ConversationState.HUMAN_ATTENTION.value
    assert conv.handoff_reason == HandoffReason.AMBIGUOUS_REQUEST.value

