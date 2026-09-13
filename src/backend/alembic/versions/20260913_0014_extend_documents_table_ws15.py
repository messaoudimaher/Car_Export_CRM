"""Extend documents table with customer export metadata (WS-15, TASK-1501).

Revision ID: 20260913_0014
Revises: 20260913_0013
Create Date: 2026-09-13 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260913_0014"
down_revision: str | None = "20260913_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add new metadata and status columns to documents table."""
    op.add_column(
        "documents",
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="SET NULL"),
            nullable=True,
            comment="Foreign key referencing associated sales lead",
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
            comment="Foreign key referencing customer owner",
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "uploader_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="Foreign key referencing user who uploaded the document",
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "category",
            sa.String(50),
            nullable=False,
            server_default="General",
            comment="Export document category (Carte_Grise, FCR_Certificate, Passport, General)",
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "sha256_hash",
            sa.String(64),
            nullable=True,
            comment="Server-side verified SHA-256 checksum hex string",
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "scan_status",
            sa.String(20),
            nullable=False,
            server_default="Pending",
            comment="Malware and integrity scan status (Pending, Passed, Quarantined)",
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="Pending",
            comment="Document lifecycle state (Pending, Available, Quarantined, Deleted)",
        ),
    )

    op.create_index("ix_documents_lead_id", "documents", ["lead_id"])
    op.create_index("ix_documents_customer_id", "documents", ["customer_id"])
    op.create_index("ix_documents_uploader_id", "documents", ["uploader_id"])
    op.create_index("ix_documents_category", "documents", ["category"])
    op.create_index("ix_documents_status", "documents", ["status"])


def downgrade() -> None:
    """Drop columns added in WS-15 migration."""
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_category", table_name="documents")
    op.drop_index("ix_documents_uploader_id", table_name="documents")
    op.drop_index("ix_documents_customer_id", table_name="documents")
    op.drop_index("ix_documents_lead_id", table_name="documents")

    op.drop_column("documents", "status")
    op.drop_column("documents", "scan_status")
    op.drop_column("documents", "sha256_hash")
    op.drop_column("documents", "category")
    op.drop_column("documents", "uploader_id")
    op.drop_column("documents", "customer_id")
    op.drop_column("documents", "lead_id")
