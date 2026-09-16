"""End-to-End RAG Integration Test (WS-13, WS-12, SEC-007, ADR 0011).

Validates the complete multi-tenant pipeline:
Ingest document -> Generate vector embeddings -> Retrieve strictly within tenant scope ->
Build grounded XML context -> Generate HITL suggestion -> Require human approval before mutation.
"""

import uuid

import pytest

from app.adapters.llm_demo import DemoLLMAdapter
from app.core.database import check_database_health, get_db_session
from app.models.ai_suggestion import AISuggestionStatus
from app.models.conversation import WhatsAppConversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.tenant import Tenant
from app.schemas.knowledge import KnowledgeDocumentIngestRequest
from app.services.ai_suggestion_service import AISuggestionService
from app.services.knowledge_service import KnowledgeService
from app.services.rag_service import RAGService


@pytest.mark.asyncio
async def test_end_to_end_rag_pipeline_with_tenant_isolation_and_hitl() -> None:
    """Verify end-to-end RAG pipeline enforces tenant isolation and HITL safety."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database unavailable for integration test.")

    async for session in get_db_session():
        # 1. Setup Tenant A and Tenant B
        tenant_a = Tenant(
            name=f"Tenant A Export {uuid.uuid4().hex[:6]}",
            slug=f"export-a-{uuid.uuid4().hex[:6]}",
        )
        tenant_b = Tenant(
            name=f"Tenant B Export {uuid.uuid4().hex[:6]}",
            slug=f"export-b-{uuid.uuid4().hex[:6]}",
        )
        session.add_all([tenant_a, tenant_b])
        await session.flush()

        # Customer & Conversation for Tenant A
        customer_a = Customer(
            tenant_id=tenant_a.id,
            first_name="Moncef",
            last_name="Ben Salem",
            phone_e164=f"+21698{uuid.uuid4().int % 1000000:06d}",
        )
        session.add(customer_a)
        await session.flush()

        conv_a = WhatsAppConversation(
            tenant_id=tenant_a.id,
            customer_id=customer_a.id,
            whatsapp_chat_id=f"chat_{uuid.uuid4().hex[:8]}",
        )
        session.add(conv_a)
        await session.flush()

        inbound_msg = Message(
            tenant_id=tenant_a.id,
            conversation_id=conv_a.id,
            direction="Inbound",
            sender_type="Customer",
            message_type="text",
            content_text="What is the tax rate for car import under FCR?",
            status="Received",
        )
        session.add(inbound_msg)
        await session.commit()

        llm_adapter = DemoLLMAdapter()
        knowledge_service = KnowledgeService(session=session, embedding_provider=llm_adapter)
        rag_service = RAGService(session=session, embedding_provider=llm_adapter)

        # 2. Ingest document for Tenant A (FCR rules)
        doc_a_request = KnowledgeDocumentIngestRequest(
            document_name="FCR_Customs_Rules_2026.pdf",
            document_text=(
                "Tunisian FCR Privilege 2026: Expatriates returning permanently to Tunisia "
                "can import one motor vehicle with 0% customs tax under FCR category. "
                "Vehicle age must not exceed 10 years at registration."
            ),
            chunk_size=300,
            chunk_overlap=50,
        )
        ingest_a = await knowledge_service.ingest_document(
            tenant_id=tenant_a.id, request=doc_a_request
        )
        assert ingest_a.total_chunks > 0

        # 3. Ingest document for Tenant B (Confidential B pricing)
        doc_b_request = KnowledgeDocumentIngestRequest(
            document_name="Tenant_B_Internal_Pricing.pdf",
            document_text=(
                "Tenant B internal rate: Shipping to La Goulette port is 1,200 EUR fixed rate."
            ),
            chunk_size=300,
            chunk_overlap=50,
        )
        ingest_b = await knowledge_service.ingest_document(
            tenant_id=tenant_b.id, request=doc_b_request
        )
        assert ingest_b.total_chunks > 0

        # 4. Execute RAG search AS TENANT A
        query = "What is the tax rate for car import under FCR?"
        results_a = await rag_service.search_relevant_chunks(
            tenant_id=tenant_a.id, query_text=query, top_k=5
        )

        # Assert Tenant A ONLY receives Tenant A chunks (SEC-007)
        assert len(results_a) > 0
        for chunk in results_a:
            assert chunk.tenant_id == tenant_a.id
            assert chunk.tenant_id != tenant_b.id
            assert "Tenant B internal rate" not in chunk.chunk_content

        # 5. Build grounded XML context string for Tenant A
        context_xml = await rag_service.search_and_format_context(
            tenant_id=tenant_a.id, query_text=query
        )
        assert "<knowledge_context>" in context_xml
        assert "FCR_Customs_Rules_2026.pdf" in context_xml

        # 6. Generate AI response suggestion using grounded context and AISuggestionService
        suggestion_service = AISuggestionService(llm_provider=llm_adapter)
        suggestion = await suggestion_service.generate_suggestion(
            db=session,
            tenant_id=tenant_a.id,
            conversation_id=conv_a.id,
            customer_id=customer_a.id,
        )

        assert suggestion.suggested_text != ""
        assert suggestion.tenant_id == tenant_a.id
        # HITL Security Guardrail: Suggestion status MUST be Suggested_Not_Sent
        assert suggestion.status == AISuggestionStatus.SUGGESTED_NOT_SENT.value

        break
