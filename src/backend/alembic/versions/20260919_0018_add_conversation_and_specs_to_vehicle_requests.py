"""Add conversation_id, color, and additional_requirements to vehicle_requests table.

Revision ID: 20260919_0018
Revises: 20260919_0017
Create Date: 2026-09-19 17:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260919_0018"
down_revision: str | None = "20260919_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vehicle_requests",
        sa.Column(
            "conversation_id",
            sa.UUID(),
            nullable=True,
            comment="Foreign key referencing parent WhatsApp conversation thread",
        ),
    )
    op.add_column(
        "vehicle_requests",
        sa.Column(
            "color",
            sa.String(length=50),
            nullable=True,
            comment="Requested exterior/interior vehicle color",
        ),
    )
    op.add_column(
        "vehicle_requests",
        sa.Column(
            "additional_requirements",
            sa.Text(),
            nullable=True,
            comment="Customer custom vehicle options, packages, or specific requirements",
        ),
    )
    op.create_foreign_key(
        "fk_vehicle_requests_conversation_id_whatsapp_conversations",
        "vehicle_requests",
        "whatsapp_conversations",
        ["conversation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_vehicle_requests_conversation_id",
        "vehicle_requests",
        ["conversation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vehicle_requests_conversation_id", table_name="vehicle_requests")
    op.drop_constraint(
        "fk_vehicle_requests_conversation_id_whatsapp_conversations",
        "vehicle_requests",
        type_="foreignkey",
    )
    op.drop_column("vehicle_requests", "additional_requirements")
    op.drop_column("vehicle_requests", "color")
    op.drop_column("vehicle_requests", "conversation_id")
