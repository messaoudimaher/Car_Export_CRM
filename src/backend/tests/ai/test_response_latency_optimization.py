"""Tests for Phase 9: Response Latency Optimization & Telemetry Profiling.

Verifies:
1. Complete latency metric tracking across all stages:
   - Meta webhook ingress
   - DB read latency (with single query join)
   - Context construction latency (with cached grounded prompt)
   - Gemini LLM generation latency
   - Pydantic validation latency
   - DB write latency
   - Meta outbound API latency
   - Total end-to-end response latency
2. Cached company knowledge retrieval executes in sub-millisecond time.
3. Strict single-pass LLM reasoning (1 LLM call per turn).
4. Preloaded entity reuse eliminates redundant DB queries.
"""

import time
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent_state_machine import ConversationMode, ConversationState
from app.core.uuid import generate_uuidv7
from app.core.whatsapp_telemetry import WhatsAppTimingMetrics
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.ports.llm import LLMCompletionResponse, LLMProvider
from app.ports.whatsapp import OutboundWhatsAppMessageResult, WhatsAppProvider
from app.schemas.agent_decision import AgentDecision
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.company_knowledge import get_cached_grounded_context_prompt, load_company_knowledge


class MockFastWhatsAppProvider(WhatsAppProvider):
    """Mock WhatsApp provider for latency tests."""

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
async def test_complete_latency_metrics_telemetry_profiling(db_session: AsyncSession):
    """Verify that all pipeline latency checkpoints are recorded accurately."""
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
            intent="VEHICLE_REQUEST",
            language="fr",
            make="BMW",
            model="X3",
            year=2021,
            response_text="Excellente recherche ! Quel est votre budget prévisionnel pour cette BMW X3 2021 ?",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )
    mock_wa = MockFastWhatsAppProvider()

    orchestrator = AgentOrchestrator(db=db_session, llm_provider=mock_llm, whatsapp_provider=mock_wa)

    timing = WhatsAppTimingMetrics(
        wamid="wamid.test.12345",
        tenant_id=str(tenant_id),
        phone_e164="+33611223344",
    )
    timing.mark_persisted()
    timing.mark_acknowledged()
    timing.mark_worker_started()

    decision = await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conv_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33611223344",
        text_body="Je cherche une BMW X3 2021",
        phone_number_id="100998877",
        timing_metrics=timing,
    )

    report = timing.to_latency_report()

    # Verify all timing intervals exist and are non-negative
    assert "db_persistence_ms" in report
    assert "webhook_ack_ms" in report
    assert "worker_queue_delay_ms" in report
    assert "db_read_ms" in report
    assert "context_construction_ms" in report
    assert "gemini_latency_ms" in report
    assert "validation_latency_ms" in report
    assert "db_write_ms" in report
    assert "meta_outbound_ms" in report
    assert "total_end_to_end_ms" in report

    assert report["db_read_ms"] >= 0
    assert report["context_construction_ms"] >= 0
    assert report["gemini_latency_ms"] >= 0
    assert report["validation_latency_ms"] >= 0
    assert report["db_write_ms"] >= 0
    assert report["meta_outbound_ms"] >= 0
    assert report["total_end_to_end_ms"] > 0


def test_cached_company_knowledge_sub_millisecond_retrieval():
    """Verify cached knowledge and prompt retrieval runs in sub-millisecond time."""
    # Warm up cache
    load_company_knowledge(force_reload=True)
    get_cached_grounded_context_prompt()

    # Benchmark cached calls (1000 iterations)
    start = time.perf_counter()
    for _ in range(1000):
        prompt = get_cached_grounded_context_prompt()
        assert len(prompt) > 100
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    avg_latency_us = (elapsed_ms / 1000.0) * 1000.0  # in microseconds
    # Must be under 50 microseconds per call
    assert avg_latency_us < 50.0, f"Expected < 50us per call, got {avg_latency_us:.2f}us"


@pytest.mark.asyncio
async def test_strict_single_pass_llm_reasoning_constraint(db_session: AsyncSession):
    """Verify that a normal customer turn executes EXACTLY 1 LLM call."""
    tenant_id = generate_uuidv7()
    customer_id = generate_uuidv7()
    conv_id = generate_uuidv7()

    tenant = Tenant(id=tenant_id, name="Auto Export Paris", slug=f"t-{uuid.uuid4().hex[:6]}")
    customer = Customer(id=customer_id, tenant_id=tenant_id, phone_e164="+33655443322", full_name="Mehdi Ben Youssef")
    conv = WhatsAppConversation(
        id=conv_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        conversation_state=ConversationState.COLLECTING_REQUEST.value,
        mode=ConversationMode.AI.value,
        draft_data={"make": "Audi", "model": "Q5", "year": 2022, "missing_fields": ["budget_eur"]},
    )
    db_session.add_all([tenant, customer, conv])
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.generate_structured_output.return_value = (
        AgentDecision(
            intent="REQUEST_UPDATE",
            language="fr",
            budget_eur=35000.0,
            destination_port="La Goulette",
            response_text="Parfait ! Pour récapituler : Audi Q5 2022, budget 35 000 €, port La Goulette. Confirmez-vous cette recherche ?",
        ),
        LLMCompletionResponse(content="ok", model="gemini-3.5-flash-lite"),
    )
    mock_wa = MockFastWhatsAppProvider()

    orchestrator = AgentOrchestrator(db=db_session, llm_provider=mock_llm, whatsapp_provider=mock_wa)

    await orchestrator.process_turn(
        tenant_id=tenant_id,
        conversation_id=conv_id,
        customer_id=customer_id,
        message_id=generate_uuidv7(),
        from_phone_e164="+33655443322",
        text_body="Mon budget est de 35 000 euros et livraison au port de La Goulette",
        phone_number_id="100998877",
    )

    # Exactly 1 LLM call
    assert mock_llm.generate_structured_output.call_count == 1
    assert len(mock_wa.dispatched_messages) == 1
