"""Knowledge Base Management & Ingestion REST API v1 Endpoints (WS-13, TASK-1303, ADR 0011)."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentUser,
    get_current_tenant_id,
    get_current_user,
    get_embedding_provider,
    require_roles,
)
from app.core.database import get_db_session
from app.models.user import UserRole
from app.ports.embedding import EmbeddingProvider
from app.schemas.knowledge import (
    KnowledgeChunkRead,
    KnowledgeDocumentIngestRequest,
    KnowledgeDocumentIngestResult,
    KnowledgeSearchRequest,
    KnowledgeSearchResult,
)
from app.services.knowledge_service import KnowledgeService
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
    service = KnowledgeService(session=session, embedding_provider=embedding_provider)
    return await service.ingest_document(tenant_id=tenant_id, request=request)


@router.get(
    "",
    response_model=list[KnowledgeChunkRead],
    status_code=status.HTTP_200_OK,
)
async def list_knowledge_chunks(
    document_name: str | None = Query(None, description="Filter chunks by document title"),
    document_id: UUID | None = Query(None, description="Filter chunks by document UUID"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Record offset"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(get_current_user),
) -> list[KnowledgeChunkRead]:
    """List tenant knowledge chunks under strict tenant scoping."""
    service = KnowledgeService(session=session)
    return await service.list_chunks(
        tenant_id=tenant_id,
        document_name=document_name,
        document_id=document_id,
        limit=limit,
        offset=offset,
    )


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
    service = KnowledgeService(session=session)
    await service.delete_chunk(tenant_id=tenant_id, chunk_id=chunk_id)


@router.delete(
    "/document/id/{document_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_knowledge_document_by_id(
    document_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(require_roles(UserRole.TENANT_ADMIN, UserRole.SUPER_ADMIN)),
) -> dict[str, Any]:
    """Bulk delete all vector chunks associated with a stable document UUID under tenant context."""
    service = KnowledgeService(session=session)
    return await service.delete_document_by_id(tenant_id=tenant_id, document_id=document_id)


@router.delete(
    "/document/{document_name}",
    status_code=status.HTTP_200_OK,
)
async def delete_knowledge_document_by_name(
    document_name: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_db_session),
    _: CurrentUser = Depends(require_roles(UserRole.TENANT_ADMIN, UserRole.SUPER_ADMIN)),
) -> dict[str, Any]:
    """Bulk delete all vector chunks associated with a document name under tenant context."""
    service = KnowledgeService(session=session)
    return await service.delete_document_by_name(tenant_id=tenant_id, document_name=document_name)
