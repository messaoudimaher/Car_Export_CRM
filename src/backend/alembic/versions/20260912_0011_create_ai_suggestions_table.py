"""Create ai_suggestions table for sales rep draft reply suggestions.

Revision ID: 20260912_0011
Revises: 20260912_0010
Create Date: 2026-09-12 22:42:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260912_0011"
down_revision: str | None = "20260912_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_suggestions",
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
            nullable=False,
            comment="Foreign key referencing target conversation thread",
        ),
        sa.Column(
            "customer_id",
            sa.UUID(),
            nullable=True,
            comment="Foreign key referencing target customer profile",
        ),
        sa.Column(
            "understanding_id",
            sa.UUID(),
            nullable=True,
            comment="Foreign key referencing parent AI understanding extraction",
        ),
        sa.Column(
            "suggested_text",
            sa.Text(),
            nullable=False,
            comment="Draft response text generated for sales representative pre-fill",
        ),
        sa.Column(
            "target_language",
            sa.String(length=10),
            server_default="fr",
            nullable=False,
            comment="Target customer language code (fr, en, ar, derja)",
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="Suggested_Not_Sent",
            nullable=False,
            comment="Lifecycle state (Suggested_Not_Sent, Accepted, Edited_And_Sent, Rejected)",
        ),
        sa.Column(
            "model_name",
            sa.String(length=50),
            server_default="gpt-4o-mini",
            nullable=False,
            comment="LLM provider model identifier used for suggestion",
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
            "status IN ('Suggested_Not_Sent', 'Accepted', 'Edited_And_Sent', 'Rejected')",
            name="ck_ai_suggestions_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["whatsapp_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["understanding_id"], ["ai_understandings.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_suggestions_tenant_id", "ai_suggestions", ["tenant_id"], unique=False)
    op.create_index(
        "ix_ai_suggestions_conversation_id", "ai_suggestions", ["conversation_id"], unique=False
    )
    op.create_index(
        "ix_ai_suggestions_customer_id", "ai_suggestions", ["customer_id"], unique=False
    )
    op.create_index(
        "ix_ai_suggestions_understanding_id", "ai_suggestions", ["understanding_id"], unique=False
    )
    op.create_index("ix_ai_suggestions_status", "ai_suggestions", ["status"], unique=False)
    op.create_index("ix_ai_suggestions_created_at", "ai_suggestions", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ai_suggestions_created_at", table_name="ai_suggestions")
    op.drop_index("ix_ai_suggestions_status", table_name="ai_suggestions")
    op.drop_index("ix_ai_suggestions_understanding_id", table_name="ai_suggestions")
    op.drop_index("ix_ai_suggestions_customer_id", table_name="ai_suggestions")
    op.drop_index("ix_ai_suggestions_conversation_id", table_name="ai_suggestions")
    op.drop_index("ix_ai_suggestions_tenant_id", table_name="ai_suggestions")
    op.drop_table("ai_suggestions")
