"""Unit & DB isolation tests for RAGService vector search (WS-13, TASK-1302, SEC-007)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.llm_demo import DemoLLMAdapter
from app.core.database import check_database_health, get_db_session
from app.models.knowledge import KnowledgeEmbedding
from app.models.tenant import Tenant
from app.services.rag_service import RAGService


@pytest.mark.asyncio
async def test_rag_service_requires_tenant_id() -> None:
    """Verify RAGService raises ValueError if tenant_id is missing or None (SEC-007)."""
    session_mock = AsyncMock()
    llm_adapter = DemoLLMAdapter()
    service = RAGService(session=session_mock, embedding_provider=llm_adapter)

    with pytest.raises(ValueError, match="tenant_id is strictly mandatory"):
        # Cast None to uuid.UUID for typing test
        await service.search_relevant_chunks(tenant_id=None, query_text="FCR rules")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_rag_service_empty_query() -> None:
    """Verify empty query string returns empty result list without hitting DB."""
    session_mock = AsyncMock()
    llm_adapter = DemoLLMAdapter()
    service = RAGService(session=session_mock, embedding_provider=llm_adapter)

    results = await service.search_relevant_chunks(tenant_id=uuid.uuid4(), query_text="   ")
    assert results == []
    session_mock.execute.assert_not_called()


@pytest.mark.asyncio
async def test_rag_service_mock_retrieval_and_formatting() -> None:
    """Verify search_relevant_chunks maps rows and formats prompt context correctly."""
    tenant_id = uuid.uuid4()
    mock_chunk = KnowledgeEmbedding(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_name="Tunisia_Customs_2026.pdf",
        chunk_index=0,
        chunk_content="Tunisian customs duty rate for vehicles imported under FCR is 0%.",
        metadata_jsonb={"section": "Duties"},
    )

    session_mock = AsyncMock()
    execute_result = MagicMock()
    execute_result.all.return_value = [(mock_chunk, 0.925)]
    session_mock.execute.return_value = execute_result

    llm_adapter = DemoLLMAdapter()
    service = RAGService(session=session_mock, embedding_provider=llm_adapter)

    results = await service.search_relevant_chunks(
        tenant_id=tenant_id, query_text="What is the duty rate under FCR?"
    )

    assert len(results) == 1
    assert results[0].document_name == "Tunisia_Customs_2026.pdf"
    assert results[0].similarity_score == pytest.approx(0.925, abs=1e-3)

    formatted_xml = await service.search_and_format_context(
        tenant_id=tenant_id, query_text="What is the duty rate under FCR?"
    )

    assert "<knowledge_context>" in formatted_xml
    assert 'name="Tunisia_Customs_2026.pdf"' in formatted_xml
    assert "Tunisian customs duty rate for vehicles imported under FCR is 0%." in formatted_xml


@pytest.mark.asyncio
async def test_rag_service_cross_tenant_vector_isolation_db() -> None:
    """Integration test asserting ZERO cross-tenant vector retrieval (SEC-007)."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not available for integration test.")

    async for session in get_db_session():
        # Create Tenant A and Tenant B
        tenant_a = Tenant(
            company_name=f"Tenant A {uuid.uuid4().hex[:6]}",
            subdomain=f"tenant-a-{uuid.uuid4().hex[:6]}",
        )
        tenant_b = Tenant(
            company_name=f"Tenant B {uuid.uuid4().hex[:6]}",
            subdomain=f"tenant-b-{uuid.uuid4().hex[:6]}",
        )
        session.add_all([tenant_a, tenant_b])
        await session.flush()

        # Both tenants have a document about "FCR Import Policy" with identical embeddings
        embedding_vector = [0.1] * 1536

        chunk_a = KnowledgeEmbedding(
            tenant_id=tenant_a.id,
            document_name="Policy_A.pdf",
            chunk_index=0,
            chunk_content="Tenant A secret export pricing policy: 5% margin.",
            embedding=embedding_vector,
            metadata_jsonb={"tenant": "A"},
        )

        chunk_b = KnowledgeEmbedding(
            tenant_id=tenant_b.id,
            document_name="Policy_B.pdf",
            chunk_index=0,
            chunk_content="Tenant B confidential client terms: 12% margin.",
            embedding=embedding_vector,
            metadata_jsonb={"tenant": "B"},
        )

        session.add_all([chunk_a, chunk_b])
        await session.commit()

        llm_adapter = DemoLLMAdapter()
        service = RAGService(session=session, embedding_provider=llm_adapter)

        # Perform search AS TENANT A
        results_a = await service.search_relevant_chunks(
            tenant_id=tenant_a.id,
            query_text="secret export pricing policy",
            top_k=10,
        )

        # Assert Tenant A ONLY gets Tenant A's chunks
        assert len(results_a) > 0
        for r in results_a:
            assert r.tenant_id == tenant_a.id
            assert r.tenant_id != tenant_b.id
            assert "Tenant B" not in r.chunk_content

        # Perform search AS TENANT B
        results_b = await service.search_relevant_chunks(
            tenant_id=tenant_b.id,
            query_text="secret export pricing policy",
            top_k=10,
        )

        # Assert Tenant B ONLY gets Tenant B's chunks
        assert len(results_b) > 0
        for r in results_b:
            assert r.tenant_id == tenant_b.id
            assert r.tenant_id != tenant_a.id
            assert "Tenant A" not in r.chunk_content

        break
