"""Create pgvector extension and knowledge_embeddings table for tenant RAG retrieval.

Revision ID: 20260913_0012
Revises: 20260912_0011
Create Date: 2026-09-13 15:24:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260913_0012"
down_revision: str | None = "20260912_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enable pgvector extension (ADR 0011)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create knowledge_embeddings table
    op.create_table(
        "knowledge_embeddings",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            comment="Time-ordered UUIDv7 primary key (ADR 0005)",
        ),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            nullable=False,
            comment="Foreign key referencing parent tenant organization",
        ),
        sa.Column(
            "document_id",
            sa.UUID(),
            nullable=True,
            comment="Foreign key referencing source document metadata",
        ),
        sa.Column(
            "document_name",
            sa.String(length=255),
            nullable=False,
            comment="User-facing source document or title string",
        ),
        sa.Column(
            "chunk_index",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Zero-based sequential chunk index within source document",
        ),
        sa.Column(
            "chunk_content",
            sa.Text(),
            nullable=False,
            comment="Text chunk body extracted from source document",
        ),
        sa.Column(
            "embedding",
            Vector(1536),
            nullable=True,
            comment="1536-dimensional vector embedding for text-embedding-3-small (ADR 0011)",
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Extensible chunk metadata JSON (section, headings, page_number)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation UTC timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update UTC timestamp",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. Create relational & vector indexes
    op.create_index(
        "ix_knowledge_embeddings_tenant_id",
        "knowledge_embeddings",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_embeddings_document_id",
        "knowledge_embeddings",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_embeddings_created_at",
        "knowledge_embeddings",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_embeddings_tenant_document",
        "knowledge_embeddings",
        ["tenant_id", "document_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_embeddings_embedding_hnsw",
        "knowledge_embeddings",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_embeddings_embedding_hnsw",
        table_name="knowledge_embeddings",
        postgresql_using="hnsw",
    )
    op.drop_index("ix_knowledge_embeddings_tenant_document", table_name="knowledge_embeddings")
    op.drop_index("ix_knowledge_embeddings_created_at", table_name="knowledge_embeddings")
    op.drop_index("ix_knowledge_embeddings_document_id", table_name="knowledge_embeddings")
    op.drop_index("ix_knowledge_embeddings_tenant_id", table_name="knowledge_embeddings")
    op.drop_table("knowledge_embeddings")
