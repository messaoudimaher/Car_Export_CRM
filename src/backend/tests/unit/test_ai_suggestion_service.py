"""Unit and DB integration tests for AISuggestionService (WS-12, ADR 0012, ADR 0014)."""

import uuid
from datetime import UTC, datetime

import pytest

from app.adapters.llm_demo import DemoLLMAdapter
from app.core.database import check_database_health, get_db_session
from app.models.ai_suggestion import AISuggestion, AISuggestionStatus
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.tenant import Tenant
from app.ports.llm import LLMCompletionRequest, LLMCompletionResponse
from app.schemas.ai_suggestion import (
    AISuggestionCreate,
    AISuggestionRead,
    AISuggestionUpdateStatus,
)
from app.services.ai_cost_tracker import AICostTracker
from app.services.ai_suggestion_service import AISuggestionService


class MockLLMAdapter(DemoLLMAdapter):
    """Mock LLM Adapter returning controlled completion responses for testing."""

    def __init__(
        self,
        response_text: str = "Bonjour, nous avons bien reçu votre demande pour la Golf 7.",
    ) -> None:
        super().__init__()
        self.response_text = response_text
        self.last_request: LLMCompletionRequest | None = None

    async def generate_text(self, request: LLMCompletionRequest) -> LLMCompletionResponse:
        self.last_request = request
        return LLMCompletionResponse(
            content=self.response_text,
            model=request.model,
            prompt_tokens=150,
            completion_tokens=40,
            total_tokens=190,
            latency_ms=12.5,
            finish_reason="stop",
            raw_response={"mock": True},
        )


def test_ai_suggestion_model_in_memory_defaults() -> None:
    """Verify in-memory model instantiation sets expected defaults."""
    tenant_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    suggestion = AISuggestion(
        tenant_id=tenant_id,
        conversation_id=conv_id,
        suggested_text="Draft reply",
    )

    assert suggestion.tenant_id == tenant_id
    assert suggestion.conversation_id == conv_id
    assert suggestion.status == AISuggestionStatus.SUGGESTED_NOT_SENT.value
    assert suggestion.target_language == "fr"
    assert suggestion.model_name == "gpt-4o-mini"
    assert suggestion.prompt_version == "v1.0"


def test_ai_suggestion_pydantic_schemas() -> None:
    """Verify Pydantic DTO schemas serialize and validate expected fields."""
    tenant_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    create_dto = AISuggestionCreate(
        tenant_id=tenant_id,
        conversation_id=conv_id,
        suggested_text="Proposed sales reply text",
        target_language="fr",
    )

    assert create_dto.tenant_id == tenant_id
    assert create_dto.status == "Suggested_Not_Sent"

    update_dto = AISuggestionUpdateStatus(status=AISuggestionStatus.ACCEPTED)
    assert update_dto.status == AISuggestionStatus.ACCEPTED

    read_dto = AISuggestionRead(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        conversation_id=conv_id,
        customer_id=None,
        understanding_id=None,
        suggested_text="Proposed draft",
        target_language="fr",
        status="Suggested_Not_Sent",
        model_name="gpt-4o-mini",
        prompt_version="v1.0",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert read_dto.suggested_text == "Proposed draft"


@pytest.mark.asyncio
async def test_generate_suggestion_db_and_guardrails() -> None:
    """Verify AISuggestionService generates draft and stores as Suggested_Not_Sent."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    async for db in get_db_session():
        tenant = Tenant(name="Test Suggestion Tenant", slug=f"t-{uuid.uuid4().hex[:8]}")
        customer = Customer(tenant_id=tenant.id, phone_e164="+21698111222", full_name="Moncef Trabelsi")
        conv = WhatsAppConversation(tenant_id=tenant.id, customer_id=customer.id)
        db.add_all([tenant, customer, conv])
        await db.flush()

        inbound_msg = Message(
            tenant_id=tenant.id,
            conversation_id=conv.id,
            direction="Inbound",
            sender_type="Customer",
            content="Salem, nheb nechri golf 7 tdi fcr rades kat addekhtesh el soum?",
        )
        db.add(inbound_msg)
        await db.flush()

        mock_llm = MockLLMAdapter()
        cost_tracker = AICostTracker()
        service = AISuggestionService(llm_provider=mock_llm, cost_tracker=cost_tracker)

        suggestion = await service.generate_suggestion(
            db=db,
            tenant_id=tenant.id,
            conversation_id=conv.id,
            customer_id=customer.id,
            target_language="fr",
        )

        # Assert suggestion persistence
        assert suggestion.id is not None
        assert suggestion.tenant_id == tenant.id
        assert suggestion.conversation_id == conv.id
        # CRITICAL HARD GUARDRAIL: Must be stored as Suggested_Not_Sent
        assert suggestion.status == AISuggestionStatus.SUGGESTED_NOT_SENT.value
        assert suggestion.suggested_text == mock_llm.response_text

        # Verify XML prompt wrapping (ADR 0014)
        assert mock_llm.last_request is not None
        user_prompt = mock_llm.last_request.prompt
        assert "<untrusted_user_message>" in user_prompt
        assert "</untrusted_user_message>" in user_prompt
        assert "<conversation_history>" in user_prompt
        assert "Salem, nheb nechri golf 7 tdi fcr rades" in user_prompt

        await db.rollback()
        break


@pytest.mark.asyncio
async def test_get_list_and_update_suggestion_status_db() -> None:
    """Verify querying, listing, and status updates for AI suggestions."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not reachable")

    async for db in get_db_session():
        tenant = Tenant(name="Test Suggestion List Tenant", slug=f"t-{uuid.uuid4().hex[:8]}")
        customer = Customer(tenant_id=tenant.id, phone_e164="+21698222333", full_name="Ines Gharbi")
        conv = WhatsAppConversation(tenant_id=tenant.id, customer_id=customer.id)
        db.add_all([tenant, customer, conv])
        await db.flush()

        mock_llm = MockLLMAdapter()
        service = AISuggestionService(llm_provider=mock_llm)

        sug1 = await service.generate_suggestion(
            db=db,
            tenant_id=tenant.id,
            conversation_id=conv.id,
            customer_id=customer.id,
        )

        fetched = await AISuggestionService.get_suggestion_by_id(
            db=db,
            tenant_id=tenant.id,
            suggestion_id=sug1.id,
        )
        assert fetched is not None
        assert fetched.id == sug1.id

        # List suggestions
        slist = await AISuggestionService.list_suggestions_for_conversation(
            db=db,
            tenant_id=tenant.id,
            conversation_id=conv.id,
        )
        assert len(slist) == 1

        # Update status
        accepted = await AISuggestionService.update_status(
            db=db,
            tenant_id=tenant.id,
            suggestion_id=sug1.id,
            new_status=AISuggestionStatus.ACCEPTED,
        )
        assert accepted.status == AISuggestionStatus.ACCEPTED.value

        # Invalid status check
        with pytest.raises(ValueError, match="Invalid AISuggestionStatus value"):
            await AISuggestionService.update_status(
                db=db,
                tenant_id=tenant.id,
                suggestion_id=sug1.id,
                new_status="UnknownStatus",
            )

        await db.rollback()
        break
