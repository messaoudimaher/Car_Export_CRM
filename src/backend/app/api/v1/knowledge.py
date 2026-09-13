"""Knowledge Base Management & Ingestion REST API v1 Endpoints (WS-13, TASK-1303, ADR 0011)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentUser,
    get_current_tenant_id,
    get_current_user,
    get_embedding_provider,
    require_roles,
)
from app.core.database import get_db_session
from app.core.errors import NotFoundException, ValidationException
from app.models.knowledge import KnowledgeEmbedding
from app.models.user import UserRole
from app.ports.embedding import EmbeddingProvider, EmbeddingRequest
from app.schemas.knowledge import (
    KnowledgeChunkRead,
    KnowledgeDocumentIngestRequest,
    KnowledgeDocumentIngestResult,
    KnowledgeSearchRequest,
    KnowledgeSearchResult,
)
from app.services.knowledge_chunker import KnowledgeChunker
from app.services.rag_service import RAGService

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


@router.post(
    "/ingest",
    response_model=KnowledgeDocumentIngestResult,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_knowledge_document(
    request: KnowledgeDocumentIngestRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    _: CurrentUser = Depends(require_roles(UserRole.TENANT_ADMIN, UserRole.SUPER_ADMIN)),
) -> KnowledgeDocumentIngestResult:
    """Ingest and chunk a tenant knowledge document into vector embeddings (ADR 0011)."""
    cleaned_text = request.document_text.strip()
    if not cleaned_text:
        raise ValidationException("document_text cannot be blank or empty.")

    # 1. Split text into sliding-window chunks
    chunker = KnowledgeChunker(
        default_chunk_size=request.chunk_size,
        default_chunk_overlap=request.chunk_overlap,
    )
    chunk_payloads = chunker.chunk_text(
        text=cleaned_text,
        extra_metadata={"document_name": request.document_name},
    )

    if not chunk_payloads:
        raise ValidationException("Document chunking produced zero valid chunks.")

    # 2. Extract chunk texts and request vector embeddings
    chunk_texts = [c["chunk_content"] for c in chunk_payloads]
    embedding_res = await embedding_provider.generate_embeddings(
        EmbeddingRequest(
            texts=chunk_texts,
            tenant_id=str(tenant_id),
        )
    )

    embeddings_list = embedding_res.embeddings

    # 3. Create KnowledgeEmbedding records
    created_entities: list[KnowledgeEmbedding] = []
    for idx, payload in enumerate(chunk_payloads):
        vec = embeddings_list[idx] if idx < len(embeddings_list) else None
        entity = KnowledgeEmbedding(
            tenant_id=tenant_id,
            document_id=request.document_id,
            document_name=request.document_name,
            chunk_index=payload["chunk_index"],
            chunk_content=payload["chunk_content"],
            embedding=vec,
            metadata_jsonb=payload["metadata_jsonb"],
        )
        created_entities.append(entity)
        session.add(entity)

    await session.commit()
    for e in created_entities:
        await session.refresh(e)

    chunk_ids = [e.id for e in created_entities]

    return KnowledgeDocumentIngestResult(
        document_name=request.document_name,
        total_chunks=len(chunk_ids),
        chunk_ids=chunk_ids,
    )


@router.get(
    "",
    response_model=list[KnowledgeChunkRead],
    status_code=status.HTTP_200_OK,
)
async def list_knowledge_chunks(
    document_name: str | None = Query(None, description="Filter chunks by document title"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Record offset"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> list[KnowledgeChunkRead]:
    """List tenant knowledge chunks with optional document filtering."""
    stmt = (
        select(KnowledgeEmbedding)
        .where(KnowledgeEmbedding.tenant_id == tenant_id)
        .order_by(KnowledgeEmbedding.document_name.asc(), KnowledgeEmbedding.chunk_index.asc())
        .offset(offset)
        .limit(limit)
    )

    if document_name:
        stmt = stmt.where(KnowledgeEmbedding.document_name.ilike(f"%{document_name}%"))

    result = await session.execute(stmt)
    records = result.scalars().all()

    return [KnowledgeChunkRead.model_validate(r) for r in records]


@router.post(
    "/search",
    response_model=list[KnowledgeSearchResult],
    status_code=status.HTTP_200_OK,
)
async def search_knowledge_base(
    request: KnowledgeSearchRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    _: CurrentUser = Depends(get_current_user),
) -> list[KnowledgeSearchResult]:
    """Search tenant knowledge base via RAG vector similarity engine (SEC-007)."""
    rag_service = RAGService(session=session, embedding_provider=embedding_provider)
    return await rag_service.search_relevant_chunks(
        tenant_id=tenant_id,
        query_text=request.query_text,
        top_k=request.top_k,
        min_similarity=request.min_similarity,
    )


@router.delete(
    "/{chunk_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_knowledge_chunk(
    chunk_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(require_roles(UserRole.TENANT_ADMIN, UserRole.SUPER_ADMIN)),
) -> None:
    """Delete a specific knowledge chunk record by UUID under tenant context."""
    stmt = select(KnowledgeEmbedding).where(
        KnowledgeEmbedding.id == chunk_id,
        KnowledgeEmbedding.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        raise NotFoundException(f"Knowledge chunk '{chunk_id}' not found for tenant.")

    await session.delete(record)
    await session.commit()


@router.delete(
    "/document/{document_name}",
    status_code=status.HTTP_200_OK,
)
async def delete_knowledge_document(
    document_name: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(require_roles(UserRole.TENANT_ADMIN, UserRole.SUPER_ADMIN)),
) -> dict[str, object]:
    """Bulk delete all vector chunks associated with a document name under tenant context."""
    stmt = delete(KnowledgeEmbedding).where(
        KnowledgeEmbedding.tenant_id == tenant_id,
        KnowledgeEmbedding.document_name == document_name,
    )
    result = await session.execute(stmt)
    await session.commit()

    deleted_count: int = getattr(result, "rowcount", 0)
    if deleted_count == 0:
        raise NotFoundException(
            f"No knowledge chunks found matching document_name '{document_name}'."
        )

    return {
        "message": f"Successfully deleted {deleted_count} chunks for document '{document_name}'.",
        "deleted_count": deleted_count,
    }
