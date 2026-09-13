"""KnowledgeEmbedding Entity Model (WS-13, ADR 0011, SECURITY.md Section 10)."""

import uuid
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.tenant import Tenant


class KnowledgeEmbedding(Base):
    """Declarative model storing tenant-scoped RAG vector embeddings and text chunks (ADR 0011)."""

    __tablename__ = "knowledge_embeddings"
    __table_args__ = (
        Index("ix_knowledge_embeddings_tenant_id", "tenant_id"),
        Index("ix_knowledge_embeddings_document_id", "document_id"),
        Index("ix_knowledge_embeddings_created_at", "created_at"),
        Index("ix_knowledge_embeddings_tenant_document", "tenant_id", "document_id"),
        Index(
            "ix_knowledge_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key referencing parent tenant organization",
    )

    document_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing source document metadata",
    )

    document_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User-facing source document or title string",
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        default=0,
        comment="Zero-based sequential chunk index within source document",
    )

    chunk_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Text chunk body extracted from source document",
    )

    embedding: Mapped[Any | None] = mapped_column(
        Vector(1536),
        nullable=True,
        comment="1536-dimensional vector embedding for text-embedding-3-small (ADR 0011)",
    )

    metadata_jsonb: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Extensible chunk metadata JSON (section, headings, page_number)",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="knowledge_embeddings",
    )

    document: Mapped["Document | None"] = relationship(
        "Document",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize KnowledgeEmbedding entity setting default in-memory values."""
        kw.setdefault("chunk_index", 0)
        kw.setdefault("metadata_jsonb", {})
        super().__init__(**kw)
