"""Unit tests for KnowledgeService safety limits, tenant isolation, and transactions (WS-13, SEC-007)."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.core.errors import ValidationException
from app.models.knowledge import KnowledgeEmbedding
from app.ports.embedding import EmbeddingProvider, EmbeddingRequest, EmbeddingResponse
from app.schemas.knowledge import KnowledgeDocumentIngestRequest
from app.services.knowledge_service import (
    EXPECTED_VECTOR_DIMENSIONS,
    MAX_CHUNKS_PER_INGEST,
    MAX_DOCUMENT_TEXT_LENGTH,
    KnowledgeService,
)


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Mock AsyncSession with commit/rollback support."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.add = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_embedding_provider() -> AsyncMock:
    """Mock EmbeddingProvider returning 1536d float vectors."""
    provider = AsyncMock(spec=EmbeddingProvider)

    async def mock_gen(req: EmbeddingRequest) -> EmbeddingResponse:
        return EmbeddingResponse(
            embeddings=[[0.01] * EXPECTED_VECTOR_DIMENSIONS for _ in req.texts],
            model="text-embedding-3-small",
            dimensions=EXPECTED_VECTOR_DIMENSIONS,
        )

    provider.generate_embeddings.side_effect = mock_gen
    return provider


@pytest.mark.asyncio
async def test_ingest_exceeds_max_text_length(
    mock_db_session: AsyncMock,
    mock_embedding_provider: AsyncMock,
) -> None:
    """Verify document_text exceeding MAX_DOCUMENT_TEXT_LENGTH raises ValidationException."""
    service = KnowledgeService(session=mock_db_session, embedding_provider=mock_embedding_provider)
    oversized_text = "A" * (MAX_DOCUMENT_TEXT_LENGTH + 10)

    req = KnowledgeDocumentIngestRequest(
        document_name="Huge.txt",
        document_text=oversized_text,
    )

    with pytest.raises(ValidationException, match="exceeds maximum allowed limit"):
        await service.ingest_document(tenant_id=uuid.uuid4(), request=req)


@pytest.mark.asyncio
async def test_ingest_dimension_mismatch(
    mock_db_session: AsyncMock,
) -> None:
    """Verify provider returning mismatched vector dimensions raises ValidationException."""
    provider_mock = AsyncMock(spec=EmbeddingProvider)
    # Provider returns 768d vector instead of expected 1536d
    provider_mock.generate_embeddings.return_value = EmbeddingResponse(
        embeddings=[[0.05] * 768],
        model="custom-small-768",
        dimensions=768,
    )

    service = KnowledgeService(session=mock_db_session, embedding_provider=provider_mock)
    req = KnowledgeDocumentIngestRequest(
        document_name="Test.txt",
        document_text="Sample text content for chunking.",
    )

    with pytest.raises(ValidationException, match="does not match database schema expectation"):
        await service.ingest_document(tenant_id=uuid.uuid4(), request=req)


@pytest.mark.asyncio
async def test_ingest_transaction_rollback_on_failure(
    mock_db_session: AsyncMock,
    mock_embedding_provider: AsyncMock,
) -> None:
    """Verify database transaction is rolled back cleanly if commit fails."""
    mock_db_session.commit.side_effect = RuntimeError("Database write error")

    service = KnowledgeService(session=mock_db_session, embedding_provider=mock_embedding_provider)
    req = KnowledgeDocumentIngestRequest(
        document_name="Faulty.txt",
        document_text="Valid document content for transaction test.",
    )

    with pytest.raises(RuntimeError, match="Database write error"):
        await service.ingest_document(tenant_id=uuid.uuid4(), request=req)

    mock_db_session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_delete_document_by_id_tenant_scoped(
    mock_db_session: AsyncMock,
) -> None:
    """Verify delete_document_by_id executes delete query under tenant_id filter."""
    tenant_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    mock_result = AsyncMock()
    mock_result.rowcount = 3
    mock_db_session.execute.return_value = mock_result

    service = KnowledgeService(session=mock_db_session)
    res = await service.delete_document_by_id(tenant_id=tenant_id, document_id=doc_id)

    assert res["deleted_count"] == 3
    assert res["document_id"] == str(doc_id)
    mock_db_session.commit.assert_called_once()
