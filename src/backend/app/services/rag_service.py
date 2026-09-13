"""Tenant-Isolated Vector Retrieval Engine Service (WS-13, TASK-1302, SEC-007, ADR 0011).

Provides multi-tenant vector similarity search across chunked document embeddings,
strictly enforcing database-level tenant isolation WHERE tenant_id = :tenant_id (SEC-007).
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeEmbedding
from app.ports.embedding import EmbeddingProvider, EmbeddingRequest
from app.schemas.knowledge import KnowledgeSearchResult

logger = logging.getLogger(__name__)


class RAGService:
    """Tenant-isolated RAG vector search service enforcing strict multi-tenancy (SEC-007)."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        """Initialize RAG retrieval engine with database session and embedding provider port."""
        self.session = session
        self.embedding_provider = embedding_provider

    async def search_relevant_chunks(
        self,
        tenant_id: uuid.UUID,
        query_text: str,
        top_k: int = 5,
        min_similarity: float = 0.0,
    ) -> list[KnowledgeSearchResult]:
        """Perform vector cosine similarity search strictly scoped to the specified tenant.

        Args:
            tenant_id: Mandatory target tenant UUID (SEC-007).
            query_text: Natural language user query string.
            top_k: Maximum number of knowledge chunks to return.
            min_similarity: Minimum cosine similarity threshold (0.0 to 1.0).

        Returns:
            List of KnowledgeSearchResult objects sorted by descending relevance.

        Raises:
            ValueError: If tenant_id is missing or query_text is empty.
        """
        if not tenant_id:
            raise ValueError("tenant_id is strictly mandatory for vector search (SEC-007)")

        cleaned_query = query_text.strip()
        if not cleaned_query:
            return []

        # 1. Generate query vector embedding via generic EmbeddingProvider port
        embedding_req = EmbeddingRequest(
            texts=[cleaned_query],
            tenant_id=str(tenant_id),
        )
        embedding_res = await self.embedding_provider.generate_embeddings(embedding_req)

        if not embedding_res.embeddings or not embedding_res.embeddings[0]:
            logger.warning(
                "EmbeddingProvider returned empty vector array for query",
                extra={"tenant_id": str(tenant_id)},
            )
            return []

        query_vector = embedding_res.embeddings[0]

        # 2. Build pgvector cosine similarity search query with mandatory tenant_id filter (SEC-007)
        distance_expr = KnowledgeEmbedding.embedding.cosine_distance(query_vector)
        similarity_expr = (1.0 - distance_expr).label("similarity_score")

        stmt = (
            select(KnowledgeEmbedding, similarity_expr)
            .where(KnowledgeEmbedding.tenant_id == tenant_id)  # SEC-007 Strict Tenant Filter
            .where(KnowledgeEmbedding.embedding.is_not(None))
        )

        if min_similarity > 0.0:
            stmt = stmt.where((1.0 - distance_expr) >= min_similarity)

        stmt = stmt.order_by(distance_expr.asc()).limit(top_k)

        result = await self.session.execute(stmt)
        rows = result.all()

        search_results: list[KnowledgeSearchResult] = []
        for chunk, score in rows:
            # Ensure similarity score is non-negative float
            sim_score = max(0.0, float(score)) if score is not None else 0.0
            search_results.append(
                KnowledgeSearchResult(
                    id=chunk.id,
                    tenant_id=chunk.tenant_id,
                    document_id=chunk.document_id,
                    document_name=chunk.document_name,
                    chunk_index=chunk.chunk_index,
                    chunk_content=chunk.chunk_content,
                    similarity_score=sim_score,
                    metadata_jsonb=chunk.metadata_jsonb,
                )
            )

        logger.info(
            f"RAG search retrieved {len(search_results)} tenant chunks",
            extra={
                "tenant_id": str(tenant_id),
                "top_k": top_k,
                "results_count": len(search_results),
            },
        )

        return search_results

    async def search_and_format_context(
        self,
        tenant_id: uuid.UUID,
        query_text: str,
        top_k: int = 5,
        min_similarity: float = 0.0,
    ) -> str:
        """Retrieve relevant tenant chunks and format into structured prompt context.

        Args:
            tenant_id: Target tenant UUID.
            query_text: User search query.
            top_k: Maximum chunks limit.
            min_similarity: Minimum score threshold.

        Returns:
            Formatted XML context string for injection into LLM prompt templates.
        """
        results = await self.search_relevant_chunks(
            tenant_id=tenant_id,
            query_text=query_text,
            top_k=top_k,
            min_similarity=min_similarity,
        )

        if not results:
            return ""

        formatted_blocks: list[str] = ["<knowledge_context>"]
        for item in results:
            doc_name = item.document_name
            chunk_idx = item.chunk_index
            score = item.similarity_score
            formatted_blocks.append(
                f'  <source_document name="{doc_name}" '
                f'chunk_index="{chunk_idx}" score="{score:.3f}">\n'
                f"    {item.chunk_content}\n"
                f"  </source_document>"
            )
        formatted_blocks.append("</knowledge_context>")

        return "\n".join(formatted_blocks)
