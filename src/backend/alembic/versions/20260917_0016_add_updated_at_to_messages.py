"""Add updated_at column to messages table.

Revision ID: 20260917_0016
Revises: 20260913_0015
Create Date: 2026-09-17 22:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260917_0016"
down_revision: str | None = "20260913_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record last update UTC timestamp",
        ),
    )


def downgrade() -> None:
    op.drop_column("messages", "updated_at")
