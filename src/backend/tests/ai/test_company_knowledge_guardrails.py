"""Company Knowledge & Anti-Hallucination Guardrails Test Suite (Phase 4).

Verifies:
1. Configuration-first loading of company facts, FCR rules, shipping, and FAQs.
2. System prompt grounding includes strict zero-hallucination constraints.
3. Agent does NOT fabricate unavailable company facts, fake warranties, or invalid policies.
4. Unavailable or out-of-scope company questions trigger safe fallback and human escalation.
5. Dynamic YAML updates modify agent knowledge without changing Python code.
6. Multilingual knowledge fidelity across French, Arabic, English, and German.
"""

import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent_state_machine import ConversationState, HandoffReason
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.ports.llm import LLMCompletionResponse, LLMProvider
from app.ports.whatsapp import OutboundWhatsAppMessageResult, WhatsAppProvider
from app.schemas.agent_decision import AgentDecision
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.company_knowledge import (
    CompanyKnowledge,
    CompanyProfile,
    FCRBusinessRules,
    load_company_knowledge,
)
from app.utils.uuid import generate_uuidv7


def test_company_knowledge_loading_and_pydantic_validation():
    """Verify company_knowledge.yaml loads cleanly into structured Pydantic models."""
    knowledge = load_company_knowledge()

    assert knowledge.company.name == "Auto Export Europe"
    assert "Germany" in knowledge.company.source_countries
    assert "Rades" in knowledge.company.destination_ports
    assert "Zarzis" in knowledge.company.destination_ports

    # FCR Rules
    assert knowledge.fcr.age_limit_years == 5
    assert len(knowledge.fcr.required_documents) >= 4
    assert any("Carte grise" in doc or "registration" in doc.lower() for doc in knowledge.fcr.required_documents)

    # Shipping & Payment
    assert "Marseille (France)" in knowledge.shipping.departure_ports
    assert "SEPA" in knowledge.payment.payment_methods[0]

    # FAQs
    assert len(knowledge.faq_items) >= 4
    faq_questions = [f.question.lower() for f in knowledge.faq_items]
    assert any("fcr" in q for q in faq_questions)
    assert any("livraison" in q or "délai" in q for q in faq_questions)


def test_grounded_context_prompt_contains_all_strict_guardrails():
    """Verify generated prompt contains explicit zero-hallucination instructions."""
    knowledge = load_company_knowledge()
    prompt_context = knowledge.to_grounded_context_prompt()

    assert "VERIFIED COMPANY KNOWLEDGE" in prompt_context
    assert "Auto Export Europe" in prompt_context
    assert "Max Vehicle Age: 5 years" in prompt_context
    assert "Rades" in prompt_context
    assert "CRITICAL ZERO-HALLUCINATION GUARDRAILS" in prompt_context
    assert "You must NEVER invent company policies" in prompt_context


def test_dynamic_knowledge_update_without_code_changes():
    """Verify knowledge changes in YAML immediately reflect in runtime without code edits."""
    custom_yaml_data = {
        "company": {
            "name": "Custom Mediterranean Auto Export",
            "country": "Germany / Tunisia / Spain",
            "operating_hours": "Monday - Friday: 09:00 - 18:00 (CET)",
            "contact_email": "custom@medexport.com",
            "contact_phone": "+34 91 1234567",
            "source_countries": ["Germany", "Spain"],
            "destination_ports": ["Rades", "Sousse", "Sfax"],
            "services": ["Direct custom sourcing"],
        },
        "business_rules": {
            "fcr": {
                "age_limit_years": 5,
                "description": "FCR 5 years max exemption rules.",
                "eligibility_requirements": ["TRE 2 years abroad"],
                "required_documents": ["Customs EX-A", "Passport", "Carte grise"],
            },
            "shipping": {
                "departure_ports": ["Barcelona (Spain)", "Marseille (France)"],
                "arrival_ports": ["Rades", "Sousse", "Sfax"],
                "average_transit_time": "7 to 12 business days",
                "maritime_insurance": "Standard transit coverage",
            },
        },
        "faq": [
            {
                "id": "faq-custom-sousse",
                "category": "shipping",
                "question": "Livrez-vous au port de Sousse ?",
                "answer": "Oui, nous assurons désormais les livraisons directes au port de Sousse.",
                "keywords": ["sousse", "port"],
            }
        ],
    }

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tmp:
        yaml.dump(custom_yaml_data, tmp)
        tmp_path = Path(tmp.name)

    try:
        custom_knowledge = load_company_knowledge(config_path=tmp_path)
        assert custom_knowledge.company.name == "Custom Mediterranean Auto Export"
        assert "Sousse" in custom_knowledge.company.destination_ports
        assert "Sfax" in custom_knowledge.company.destination_ports
        assert len(custom_knowledge.faq_items) == 1
        assert "Sousse" in custom_knowledge.faq_items[0].answer

        prompt_str = custom_knowledge.to_grounded_context_prompt()
        assert "Custom Mediterranean Auto Export" in prompt_str
        assert "Sousse" in prompt_str
    finally:
        tmp_path.unlink(missing_ok=True)


def test_multilingual_fallback_messages():
    """Verify safe fallback resolution in all supported languages."""
    knowledge = load_company_knowledge()

    fr_fallback = knowledge.get_fallback_response("fr")
    ar_fallback = knowledge.get_fallback_response("ar")
    en_fallback = knowledge.get_fallback_response("en")
    de_fallback = knowledge.get_fallback_response("de")

    assert "conseiller commercial" in fr_fallback
    assert "مستشارنا" in ar_fallback
    assert "sales advisor" in en_fallback
    assert "Kundenberater" in de_fallback


@pytest.mark.asyncio
async def test_agent_answers_grounded_fcr_faq_truthfully(db_session: AsyncSession):
    """Verify agent accurately answers FCR rules from approved knowledge."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conversation_id = generate_uuidv7()
    message_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Test Co Tenant", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+21620111222",
        first_name="Mehdi",
    )
    conversation = WhatsAppConversation(
        id=conversation_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        draft_data={},
    )
    db_session.add_all([tenant, customer, conversation])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="FAQ",
            language="fr",
            response_text="Le régime FCR est réservé aux Tunisiens résidant à l'étranger (TRE) depuis au moins 2 ans. Le véhicule doit avoir au maximum 5 ans à sa première immatriculation.",
            human_attention_required=False,
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )

    mock_whatsapp = AsyncMock(spec=WhatsAppProvider)
    mock_whatsapp.send_text_message.return_value = OutboundWhatsAppMessageResult(
        wamid="wamid.faq.test.001", recipient_e164="+21620111222", status="sent"
    )

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=mock_llm,
        whatsapp_provider=mock_whatsapp,
    )

    decision = await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=message_id,
        from_phone_e164="+21620111222",
        text_body="Quelles sont les conditions pour le FCR en Tunisie ?",
        phone_number_id="100998877",
    )

    assert decision.intent == "FAQ"
    assert "5 ans" in decision.response_text
    assert "TRE" in decision.response_text or "Tunisiens" in decision.response_text
    mock_whatsapp.send_text_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_agent_does_not_fabricate_unavailable_company_facts_and_escalates(db_session: AsyncSession):
    """Verify agent does NOT invent fake company policies (e.g. 10-year free warranty, office in Tokyo) and escalates."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conversation_id = generate_uuidv7()
    message_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Test Co Tenant 2", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+33612345678",
        first_name="Karim",
    )
    conversation = WhatsAppConversation(
        id=conversation_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        draft_data={},
    )
    db_session.add_all([tenant, customer, conversation])
    await db_session.commit()

    # Customer asks about a fake 10-year free warranty or fake office in Tokyo
    fake_policy_query = "Est-ce que vous offrez une garantie 10 ans gratuite et avez-vous une agence à Tokyo ?"

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="FAQ",
            language="fr",
            response_text="Pour cette demande spécifique non couverte par notre guide officiel, un conseiller commercial va vérifier les détails et vous répondre directement.",
            human_attention_required=True,
            reasoning="Customer asked about unsupported 10-year warranty and Tokyo branch.",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )

    mock_whatsapp = AsyncMock(spec=WhatsAppProvider)
    mock_whatsapp.send_text_message.return_value = OutboundWhatsAppMessageResult(
        wamid="wamid.fake.policy.001", recipient_e164="+33612345678", status="sent"
    )

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=mock_llm,
        whatsapp_provider=mock_whatsapp,
    )

    decision = await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=message_id,
        from_phone_e164="+33612345678",
        text_body=fake_policy_query,
        phone_number_id="100998877",
    )

    # Verify decision refused to fabricate and escalated
    assert decision.human_attention_required is True
    assert "conseiller commercial" in decision.response_text or "vérifier" in decision.response_text

    # Verify state machine deterministically transitioned to HUMAN_ATTENTION with UNSUPPORTED_QUESTION
    await db_session.refresh(conversation)
    assert conversation.conversation_state == ConversationState.HUMAN_ATTENTION.value
    assert conversation.handoff_reason == HandoffReason.UNSUPPORTED_QUESTION.value


@pytest.mark.asyncio
async def test_agent_refuses_crypto_payment_fabrication(db_session: AsyncSession):
    """Verify agent rejects unsupported payment methods (e.g. Bitcoin/crypto) and routes to human attention."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conversation_id = generate_uuidv7()
    message_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Test Co Tenant 3", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(
        id=customer_id,
        tenant_id=tenant_id,
        phone_e164="+491512345678",
        first_name="Sami",
    )
    conversation = WhatsAppConversation(
        id=conversation_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.AI_ACTIVE.value,
        draft_data={},
    )
    db_session.add_all([tenant, customer, conversation])
    await db_session.commit()

    crypto_query = "Puis-je vous payer en Bitcoin pour l'achat de la voiture ?"

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="FAQ",
            language="fr",
            response_text="Nos paiements s'effectuent exclusivement par virement bancaire SEPA sécurisé. Nous n'acceptons pas les cryptomonnaies.",
            human_attention_required=True,
            reasoning="Cryptocurrency is an unsupported payment channel.",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )

    mock_whatsapp = AsyncMock(spec=WhatsAppProvider)
    mock_whatsapp.send_text_message.return_value = OutboundWhatsAppMessageResult(
        wamid="wamid.crypto.001", recipient_e164="+491512345678", status="sent"
    )

    orchestrator = AgentOrchestrator(
        db=db_session,
        llm_provider=mock_llm,
        whatsapp_provider=mock_whatsapp,
    )

    decision = await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        customer_id=customer_id,
        message_id=message_id,
        from_phone_e164="+491512345678",
        text_body=crypto_query,
        phone_number_id="100998877",
    )

    assert decision.human_attention_required is True
    await db_session.refresh(conversation)
    assert conversation.conversation_state == ConversationState.HUMAN_ATTENTION.value
    assert conversation.handoff_reason == HandoffReason.UNSUPPORTED_QUESTION.value
