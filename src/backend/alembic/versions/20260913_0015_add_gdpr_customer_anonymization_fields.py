"""Add is_anonymized, anonymized_at, and legal_hold columns to customers table (WS-15, TASK-1503).

Revision ID: 20260913_0015
Revises: 20260913_0014
Create Date: 2026-09-13 17:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260913_0015"
down_revision: str | None = "20260913_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add GDPR anonymization and legal hold columns to customers table."""
    op.add_column(
        "customers",
        sa.Column(
            "is_anonymized",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="GDPR right-to-erasure anonymization status indicator",
        ),
    )
    op.add_column(
        "customers",
        sa.Column(
            "anonymized_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC timestamp when customer PII was anonymized under GDPR request",
        ),
    )
    op.add_column(
        "customers",
        sa.Column(
            "legal_hold",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Legal retention hold flag preventing automated PII erasure",
        ),
    )


def downgrade() -> None:
    """Drop GDPR anonymization columns from customers table."""
    op.drop_column("customers", "legal_hold")
    op.drop_column("customers", "anonymized_at")
    op.drop_column("customers", "is_anonymized")
