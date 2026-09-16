"""Unit and DB integration tests for KnowledgeEmbedding and KnowledgeChunker (WS-13, ADR 0011)."""

import uuid
from datetime import UTC, datetime

import pytest

from app.core.database import check_database_health, get_db_session
from app.models.knowledge import KnowledgeEmbedding
from app.models.tenant import Tenant
from app.schemas.knowledge import (
    KnowledgeChunkCreate,
    KnowledgeChunkRead,
    KnowledgeDocumentIngestRequest,
    KnowledgeDocumentIngestResult,
)
from app.services.knowledge_chunker import KnowledgeChunker


def test_knowledge_embedding_model_in_memory_defaults() -> None:
    """Verify KnowledgeEmbedding model instantiation sets expected defaults."""
    tenant_id = uuid.uuid4()
    chunk = KnowledgeEmbedding(
        tenant_id=tenant_id,
        document_name="FCR_Regulations_2026.pdf",
        chunk_content="Export regime rules for Tunisian diaspora car imports under FCR.",
    )

    assert chunk.tenant_id == tenant_id
    assert chunk.document_name == "FCR_Regulations_2026.pdf"
    assert chunk.chunk_content == "Export regime rules for Tunisian diaspora car imports under FCR."
    assert chunk.chunk_index == 0
    assert chunk.metadata_jsonb == {}
    assert chunk.embedding is None


def test_knowledge_pydantic_schemas() -> None:
    """Verify Pydantic DTO schemas validate and serialize as expected."""
    tenant_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    now = datetime.now(UTC)

    create_schema = KnowledgeChunkCreate(
        tenant_id=tenant_id,
        document_id=doc_id,
        document_name="Customs_Tariff_DE_TN.pdf",
        chunk_index=1,
        chunk_content="Duty rates for diesel engines above 2000cc are 25%.",
        embedding=[0.01] * 1536,
        metadata_jsonb={"section": "Tax Rates", "page": 4},
    )

    assert create_schema.tenant_id == tenant_id
    assert create_schema.document_name == "Customs_Tariff_DE_TN.pdf"
    assert len(create_schema.embedding or []) == 1536
    assert create_schema.metadata_jsonb["page"] == 4

    read_schema = KnowledgeChunkRead(
        id=chunk_id,
        tenant_id=tenant_id,
        document_id=doc_id,
        document_name="Customs_Tariff_DE_TN.pdf",
        chunk_index=1,
        chunk_content="Duty rates for diesel engines above 2000cc are 25%.",
        metadata_jsonb={"section": "Tax Rates"},
        created_at=now,
        updated_at=now,
    )
    assert read_schema.id == chunk_id

    ingest_req = KnowledgeDocumentIngestRequest(
        document_name="Guide_FCR.txt",
        document_text="Sample text for testing ingest request DTO validation.",
        chunk_size=500,
        chunk_overlap=50,
    )
    assert ingest_req.chunk_size == 500
    assert ingest_req.chunk_overlap == 50

    ingest_res = KnowledgeDocumentIngestResult(
        document_name="Guide_FCR.txt",
        total_chunks=1,
        chunk_ids=[chunk_id],
    )
    assert ingest_res.total_chunks == 1
    assert ingest_res.chunk_ids == [chunk_id]


def test_knowledge_chunker_short_text() -> None:
    """Verify KnowledgeChunker returns single chunk for short document."""
    chunker = KnowledgeChunker(default_chunk_size=600, default_chunk_overlap=100)
    text = "Short knowledge document for car export FCR rules."

    chunks = chunker.chunk_text(text, extra_metadata={"source": "test"})

    assert len(chunks) == 1
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["chunk_content"] == text
    assert chunks[0]["metadata_jsonb"]["source"] == "test"
    assert chunks[0]["metadata_jsonb"]["char_count"] == len(text)


def test_knowledge_chunker_sliding_window() -> None:
    """Verify KnowledgeChunker generates overlapping chunks for multi-paragraph text."""
    chunker = KnowledgeChunker()
    p1 = (
        "Paragraph 1: Tunisian car import regulations require vehicle age to be under 5 years "
        "for standard imports, or up to 10 years under FCR privilege."
    )
    p2 = (
        "Paragraph 2: Tax calculation depends on engine displacement (cc) and fuel type "
        "(petrol, diesel, hybrid, electric)."
    )
    p3 = (
        "Paragraph 3: Required documents include foreign registration certificate, "
        "purchase invoice, export declaration, and FCR certificate."
    )

    full_text = f"{p1}\n\n{p2}\n\n{p3}"

    chunks = chunker.chunk_text(full_text, chunk_size=150, chunk_overlap=30)

    assert len(chunks) > 1
    for idx, c in enumerate(chunks):
        assert c["chunk_index"] == idx
        assert "start_char" in c["metadata_jsonb"]
        assert "end_char" in c["metadata_jsonb"]
        assert len(c["chunk_content"]) > 0


def test_knowledge_chunker_validation() -> None:
    """Verify KnowledgeChunker raises ValueError on invalid configuration."""
    with pytest.raises(ValueError, match="chunk_size must be at least 50"):
        KnowledgeChunker(default_chunk_size=10)

    with pytest.raises(ValueError, match="chunk_overlap cannot be negative"):
        KnowledgeChunker(default_chunk_size=500, default_chunk_overlap=-10)

    with pytest.raises(ValueError, match="chunk_overlap must be strictly less than chunk_size"):
        KnowledgeChunker(default_chunk_size=200, default_chunk_overlap=200)


@pytest.mark.asyncio
async def test_knowledge_embedding_db_persistence() -> None:
    """Verify KnowledgeEmbedding record can be saved and queried from PostgreSQL DB."""
    if not await check_database_health():
        pytest.skip("PostgreSQL database is not available for integration test.")

    async for session in get_db_session():
        tenant = Tenant(
            name=f"RAG Test Org {uuid.uuid4().hex[:6]}",
            slug=f"rag-{uuid.uuid4().hex[:6]}",
        )
        session.add(tenant)
        await session.flush()

        knowledge_entry = KnowledgeEmbedding(
            tenant_id=tenant.id,
            document_name="Test_Ingestion.txt",
            chunk_index=0,
            chunk_content="Sample vector chunk content for db persistence test.",
            embedding=[0.05] * 1536,
            metadata_jsonb={"category": "test"},
        )
        session.add(knowledge_entry)
        await session.commit()
        await session.refresh(knowledge_entry)

        assert knowledge_entry.id is not None
        assert knowledge_entry.tenant_id == tenant.id
        assert knowledge_entry.document_name == "Test_Ingestion.txt"
        assert knowledge_entry.metadata_jsonb == {"category": "test"}
        assert len(knowledge_entry.embedding or []) == 1536
        break
