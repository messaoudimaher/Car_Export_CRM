"""Add agent state and mode columns to whatsapp_conversations table.

Revision ID: 20260919_0017
Revises: 20260917_0016
Create Date: 2026-09-19 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260919_0017"
down_revision: str | None = "20260917_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "whatsapp_conversations",
        sa.Column(
            "mode",
            sa.String(length=20),
            server_default="AI",
            nullable=False,
            comment="Conversation operational mode (AI, HUMAN)",
        ),
    )
    op.add_column(
        "whatsapp_conversations",
        sa.Column(
            "conversation_state",
            sa.String(length=50),
            server_default="AI_ACTIVE",
            nullable=False,
            comment="Autonomous state (AI_ACTIVE, WAITING_FOR_CUSTOMER, COLLECTING_REQUEST, AWAITING_REQUEST_CONFIRMATION, NEW_VEHICLE_REQUEST, HUMAN_ATTENTION, HUMAN_ACTIVE, CLOSED)",
        ),
    )
    op.add_column(
        "whatsapp_conversations",
        sa.Column(
            "handoff_reason",
            sa.String(length=100),
            nullable=True,
            comment="Reason for human handoff",
        ),
    )
    op.add_column(
        "whatsapp_conversations",
        sa.Column(
            "handoff_summary",
            sa.Text(),
            nullable=True,
            comment="AI summary for human handoff context",
        ),
    )
    op.add_column(
        "whatsapp_conversations",
        sa.Column(
            "draft_data",
            sa.JSON(),
            nullable=True,
            comment="Accumulated vehicle request draft parameters across turns",
        ),
    )
    op.create_index(
        "ix_whatsapp_conversations_mode",
        "whatsapp_conversations",
        ["mode"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_conversations_conversation_state",
        "whatsapp_conversations",
        ["conversation_state"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_whatsapp_conversations_conversation_state", table_name="whatsapp_conversations")
    op.drop_index("ix_whatsapp_conversations_mode", table_name="whatsapp_conversations")
    op.drop_column("whatsapp_conversations", "draft_data")
    op.drop_column("whatsapp_conversations", "handoff_summary")
    op.drop_column("whatsapp_conversations", "handoff_reason")
    op.drop_column("whatsapp_conversations", "conversation_state")
    op.drop_column("whatsapp_conversations", "mode")
