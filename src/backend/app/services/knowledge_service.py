"""Knowledge Service for document ingestion, chunk management, and deletion (WS-13, SEC-007)."""

import logging
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundException, ValidationException
from app.models.knowledge import KnowledgeEmbedding
from app.ports.embedding import EmbeddingProvider, EmbeddingRequest
from app.schemas.knowledge import (
    KnowledgeChunkRead,
    KnowledgeDocumentIngestRequest,
    KnowledgeDocumentIngestResult,
)
from app.services.knowledge_chunker import KnowledgeChunker

logger = logging.getLogger(__name__)

# Security and system limits for synchronous ingestion
MAX_DOCUMENT_TEXT_LENGTH = 500_000  # Max 500k characters (~100k words) per request
MAX_CHUNKS_PER_INGEST = 500  # Max 500 chunks generated per document
EXPECTED_VECTOR_DIMENSIONS = 1536  # Target vector dimension for text-embedding-3-small


class KnowledgeService:
    """Tenant-scoped Knowledge Base service enforcing strict multi-tenancy (SEC-007)."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        """Initialize KnowledgeService with database session and optional embedding provider."""
        self.session = session
        self.embedding_provider = embedding_provider

    async def ingest_document(
        self,
        tenant_id: uuid.UUID,
        request: KnowledgeDocumentIngestRequest,
    ) -> KnowledgeDocumentIngestResult:
        """Atomically chunk, embed, and persist a tenant knowledge document (SEC-007).

        Enforces:
        - Strict tenant isolation (tenant_id)
        - Max text length & chunk count boundaries
        - Provider dimension validation
        - Atomic transaction rollback on failure
        - Replacement of existing document_id chunks if document_id is specified.
        """
        if not tenant_id:
            raise ValueError("tenant_id is mandatory for document ingestion (SEC-007)")

        if not self.embedding_provider:
            raise ValidationException("EmbeddingProvider port is required for document ingestion.")

        cleaned_text = request.document_text.strip()

        if not cleaned_text:
            raise ValidationException("document_text cannot be empty or whitespace.")

        if len(cleaned_text) > MAX_DOCUMENT_TEXT_LENGTH:
            raise ValidationException(
                f"Document text length ({len(cleaned_text)} chars) exceeds maximum allowed "
                f"limit of {MAX_DOCUMENT_TEXT_LENGTH} characters."
            )

        # 1. Chunk document text using sliding window strategy
        chunker = KnowledgeChunker(
            default_chunk_size=request.chunk_size,
            default_chunk_overlap=request.chunk_overlap,
        )
        chunk_payloads = chunker.chunk_text(
            text=cleaned_text,
            extra_metadata={"document_name": request.document_name},
        )

        if not chunk_payloads:
            raise ValidationException("Document chunking yielded 0 valid chunks.")

        if len(chunk_payloads) > MAX_CHUNKS_PER_INGEST:
            raise ValidationException(
                f"Document produced {len(chunk_payloads)} chunks, exceeding the max limit "
                f"of {MAX_CHUNKS_PER_INGEST} chunks per ingestion request."
            )

        # 2. Extract texts and generate vector embeddings via EmbeddingProvider port
        chunk_texts = [c["chunk_content"] for c in chunk_payloads]
        embedding_res = await self.embedding_provider.generate_embeddings(
            EmbeddingRequest(
                texts=chunk_texts,
                tenant_id=str(tenant_id),
                dimensions=EXPECTED_VECTOR_DIMENSIONS,
            )
        )

        if not embedding_res.embeddings or len(embedding_res.embeddings) != len(chunk_texts):
            raise ValidationException(
                f"EmbeddingProvider returned {len(embedding_res.embeddings or [])} vectors "
                f"for {len(chunk_texts)} chunks."
            )

        # Validate vector dimension length
        first_vec = embedding_res.embeddings[0]
        if len(first_vec) != EXPECTED_VECTOR_DIMENSIONS:
            logger.warning(
                f"Embedding dimension mismatch: expected {EXPECTED_VECTOR_DIMENSIONS}, "
                f"got {len(first_vec)} from provider '{embedding_res.model}'.",
                extra={"tenant_id": str(tenant_id)},
            )
            raise ValidationException(
                f"Vector embedding dimension {len(first_vec)} does not match database "
                f"schema expectation of {EXPECTED_VECTOR_DIMENSIONS}."
            )

        # 3. Transactional atomic persistence
        try:
            # If a stable document_id is provided, delete pre-existing chunks for idempotency
            if request.document_id:
                await self.session.execute(
                    delete(KnowledgeEmbedding).where(
                        KnowledgeEmbedding.tenant_id == tenant_id,
                        KnowledgeEmbedding.document_id == request.document_id,
                    )
                )

            created_entities: list[KnowledgeEmbedding] = []
            for idx, payload in enumerate(chunk_payloads):
                vec = embedding_res.embeddings[idx]
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
                self.session.add(entity)

            await self.session.commit()
            for entity in created_entities:
                await self.session.refresh(entity)

            chunk_ids = [e.id for e in created_entities]

            logger.info(
                f"Ingested {len(chunk_ids)} knowledge chunks for '{request.document_name}'",
                extra={"tenant_id": str(tenant_id), "document_name": request.document_name},
            )

            return KnowledgeDocumentIngestResult(
                document_name=request.document_name,
                total_chunks=len(chunk_ids),
                chunk_ids=chunk_ids,
            )

        except Exception as e:
            await self.session.rollback()
            logger.error(
                f"Transaction rollback during document ingestion: {e}",
                extra={"tenant_id": str(tenant_id), "document_name": request.document_name},
            )
            raise

    async def list_chunks(
        self,
        tenant_id: uuid.UUID,
        document_name: str | None = None,
        document_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[KnowledgeChunkRead]:
        """List knowledge chunks under strict tenant scoping (SEC-007)."""
        if not tenant_id:
            raise ValueError("tenant_id is mandatory for listing chunks (SEC-007)")

        stmt = (
            select(KnowledgeEmbedding)
            .where(KnowledgeEmbedding.tenant_id == tenant_id)  # SEC-007 Filter
            .order_by(KnowledgeEmbedding.document_name.asc(), KnowledgeEmbedding.chunk_index.asc())
            .offset(offset)
            .limit(limit)
        )

        if document_id:
            stmt = stmt.where(KnowledgeEmbedding.document_id == document_id)
        elif document_name:
            stmt = stmt.where(KnowledgeEmbedding.document_name.ilike(f"%{document_name}%"))

        result = await self.session.execute(stmt)
        records = result.scalars().all()

        return [KnowledgeChunkRead.model_validate(r) for r in records]

    async def delete_chunk(
        self,
        tenant_id: uuid.UUID,
        chunk_id: uuid.UUID,
    ) -> None:
        """Delete a single knowledge chunk record under strict tenant context (SEC-007)."""
        if not tenant_id:
            raise ValueError("tenant_id is mandatory for chunk deletion (SEC-007)")

        stmt = select(KnowledgeEmbedding).where(
            KnowledgeEmbedding.id == chunk_id,
            KnowledgeEmbedding.tenant_id == tenant_id,  # SEC-007 Filter
        )
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            raise NotFoundException(f"Knowledge chunk '{chunk_id}' not found for tenant.")

        await self.session.delete(record)
        await self.session.commit()

    async def delete_document_by_id(
        self,
        tenant_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Bulk delete all chunks matching a stable document UUID under tenant context (SEC-007)."""
        if not tenant_id:
            raise ValueError("tenant_id is mandatory for document deletion (SEC-007)")

        stmt = delete(KnowledgeEmbedding).where(
            KnowledgeEmbedding.tenant_id == tenant_id,  # SEC-007 Filter
            KnowledgeEmbedding.document_id == document_id,
        )
        result = await self.session.execute(stmt)
        await self.session.commit()

        deleted_count: int = getattr(result, "rowcount", 0)
        if deleted_count == 0:
            raise NotFoundException(f"No knowledge chunks found for document_id '{document_id}'.")

        return {
            "message": f"Successfully deleted {deleted_count} chunks for document_id.",
            "document_id": str(document_id),
            "deleted_count": deleted_count,
        }

    async def delete_document_by_name(
        self,
        tenant_id: uuid.UUID,
        document_name: str,
    ) -> dict[str, Any]:
        """Bulk delete all chunks matching a document title under tenant context (SEC-007)."""
        if not tenant_id:
            raise ValueError("tenant_id is mandatory for document deletion (SEC-007)")

        stmt = delete(KnowledgeEmbedding).where(
            KnowledgeEmbedding.tenant_id == tenant_id,  # SEC-007 Filter
            KnowledgeEmbedding.document_name == document_name,
        )
        result = await self.session.execute(stmt)
        await self.session.commit()

        deleted_count: int = getattr(result, "rowcount", 0)
        if deleted_count == 0:
            raise NotFoundException(
                f"No knowledge chunks found matching document_name '{document_name}'."
            )

        return {
            "message": f"Successfully deleted {deleted_count} chunks for document.",
            "document_name": document_name,
            "deleted_count": deleted_count,
        }
