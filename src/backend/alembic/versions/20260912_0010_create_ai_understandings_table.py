"""Create ai_understandings table for provisional Layer 2 AI extractions.

Revision ID: 20260912_0010
Revises: 20260912_0009
Create Date: 2026-09-12 22:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260912_0010"
down_revision: str | None = "20260912_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_understandings",
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
            "conversation_id",
            sa.UUID(),
            nullable=True,
            comment="Foreign key referencing parent conversation thread",
        ),
        sa.Column(
            "message_id",
            sa.UUID(),
            nullable=True,
            comment="Foreign key referencing source customer message",
        ),
        sa.Column(
            "customer_id",
            sa.UUID(),
            nullable=True,
            comment="Foreign key referencing customer profile",
        ),
        sa.Column(
            "intent",
            sa.String(length=50),
            server_default="SOURCING_INQUIRY",
            nullable=False,
            comment="Extracted intent classification (e.g. SOURCING_INQUIRY, FCR_CUSTOMS_INQUIRY)",
        ),
        sa.Column(
            "extracted_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
            comment="Schema-validated JSON payload from LLM (AIExtractionResult)",
        ),
        sa.Column(
            "confidence_score",
            sa.Numeric(precision=4, scale=3),
            server_default="0.000",
            nullable=False,
            comment="Model confidence score between 0.000 and 1.000",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="Provisional",
            nullable=False,
            comment="Provisional extraction state (Provisional, Confirmed, Rejected)",
        ),
        sa.Column(
            "detected_language",
            sa.String(length=10),
            server_default="fr",
            nullable=False,
            comment="Detected language code (fr, en, ar, derja)",
        ),
        sa.Column(
            "summary_fr",
            sa.Text(),
            server_default="",
            nullable=False,
            comment="One-sentence French summary for agent inbox UI",
        ),
        sa.Column(
            "model_name",
            sa.String(length=50),
            server_default="gpt-4o-mini",
            nullable=False,
            comment="LLM provider model identifier used for extraction",
        ),
        sa.Column(
            "prompt_version",
            sa.String(length=20),
            server_default="v1.0",
            nullable=False,
            comment="System prompt version identifier",
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
        sa.CheckConstraint(
            "confidence_score >= 0.000 AND confidence_score <= 1.000",
            name="ck_ai_understandings_confidence_score",
        ),
        sa.CheckConstraint(
            "status IN ('Provisional', 'Confirmed', 'Rejected')",
            name="ck_ai_understandings_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["whatsapp_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_understandings_tenant_id", "ai_understandings", ["tenant_id"], unique=False
    )
    op.create_index(
        "ix_ai_understandings_conversation_id",
        "ai_understandings",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_understandings_message_id", "ai_understandings", ["message_id"], unique=False
    )
    op.create_index(
        "ix_ai_understandings_customer_id", "ai_understandings", ["customer_id"], unique=False
    )
    op.create_index("ix_ai_understandings_status", "ai_understandings", ["status"], unique=False)
    op.create_index("ix_ai_understandings_intent", "ai_understandings", ["intent"], unique=False)
    op.create_index(
        "ix_ai_understandings_created_at", "ai_understandings", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_ai_understandings_created_at", table_name="ai_understandings")
    op.drop_index("ix_ai_understandings_intent", table_name="ai_understandings")
    op.drop_index("ix_ai_understandings_status", table_name="ai_understandings")
    op.drop_index("ix_ai_understandings_customer_id", table_name="ai_understandings")
    op.drop_index("ix_ai_understandings_message_id", table_name="ai_understandings")
    op.drop_index("ix_ai_understandings_conversation_id", table_name="ai_understandings")
    op.drop_index("ix_ai_understandings_tenant_id", table_name="ai_understandings")
    op.drop_table("ai_understandings")
