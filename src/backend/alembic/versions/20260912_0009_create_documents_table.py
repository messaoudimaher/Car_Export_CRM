"""Create documents table for private object storage metadata.

Revision ID: 20260912_0009
Revises: 20260912_0008
Create Date: 2026-09-12 21:11:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260912_0009"
down_revision: str | None = "20260912_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
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
            "quotation_id",
            sa.UUID(),
            nullable=True,
            comment="Foreign key referencing parent quotation",
        ),
        sa.Column(
            "document_type",
            sa.String(length=50),
            server_default="Quotation_PDF",
            nullable=False,
            comment="Categorized document classification (e.g. Quotation_PDF, Invoice_PDF)",
        ),
        sa.Column(
            "object_key",
            sa.String(length=500),
            nullable=False,
            comment="Private object storage path (e.g. tenants/<tenant_id>/quotes/v1.pdf)",
        ),
        sa.Column(
            "file_name",
            sa.String(length=255),
            nullable=False,
            comment="User-facing file name string (e.g. QT-2026-00001.pdf)",
        ),
        sa.Column(
            "file_size_bytes",
            sa.Integer(),
            nullable=False,
            comment="Payload binary size in bytes",
        ),
        sa.Column(
            "mime_type",
            sa.String(length=100),
            server_default="application/pdf",
            nullable=False,
            comment="MIME content type (e.g. application/pdf)",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="Document version revision number",
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
        sa.ForeignKeyConstraint(["quotation_id"], ["quotations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"], unique=False)
    op.create_index("ix_documents_quotation_id", "documents", ["quotation_id"], unique=False)
    op.create_index(
        "ix_documents_tenant_type",
        "documents",
        ["tenant_id", "document_type"],
        unique=False,
    )
    op.create_index("ix_documents_object_key", "documents", ["object_key"], unique=True)
    op.create_index("ix_documents_created_at", "documents", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_documents_created_at", table_name="documents")
    op.drop_index("ix_documents_object_key", table_name="documents")
    op.drop_index("ix_documents_tenant_type", table_name="documents")
    op.drop_index("ix_documents_quotation_id", table_name="documents")
    op.drop_index("ix_documents_tenant_id", table_name="documents")
    op.drop_table("documents")
