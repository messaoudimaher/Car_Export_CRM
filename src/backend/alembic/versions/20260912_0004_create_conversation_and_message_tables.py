"""Create whatsapp_conversations and messages tables.

Revision ID: 20260912_0004
Revises: 20260912_0003
Create Date: 2026-09-12 01:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "20260912_0004"
down_revision: str | None = "20260912_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create whatsapp_conversations table
    op.create_table(
        "whatsapp_conversations",
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
            "customer_id",
            sa.UUID(),
            nullable=False,
            comment="Foreign key referencing buyer customer profile",
        ),
        sa.Column(
            "assigned_agent_id",
            sa.UUID(),
            nullable=True,
            comment="Foreign key referencing assigned sales representative user",
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="PendingAgent",
            nullable=False,
            comment="Thread operational status (PendingAgent, Active, Resolved, Archived)",
        ),
        sa.Column(
            "last_message_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Timestamp of most recent inbound/outbound message dispatch",
        ),
        sa.Column(
            "unread_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
            comment="Count of unread inbound messages for assigned agent",
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
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_agent_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "customer_id",
            name="uq_whatsapp_conversations_tenant_id_customer_id",
        ),
    )
    op.create_index(
        "ix_whatsapp_conversations_tenant_id",
        "whatsapp_conversations",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_conversations_customer_id",
        "whatsapp_conversations",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_conversations_assigned_agent_id",
        "whatsapp_conversations",
        ["assigned_agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_conversations_status",
        "whatsapp_conversations",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_whatsapp_conversations_last_message_at",
        "whatsapp_conversations",
        ["last_message_at"],
        unique=False,
    )

    # Create messages table
    op.create_table(
        "messages",
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
            comment="Foreign key referencing parent conversation thread",
        ),
        sa.Column(
            "provider_message_id",
            sa.String(length=100),
            nullable=True,
            comment="Meta WhatsApp wamid string for deduplication (BR-008)",
        ),
        sa.Column(
            "direction",
            sa.String(length=10),
            nullable=False,
            comment="Message flow direction (Inbound, Outbound)",
        ),
        sa.Column(
            "sender_type",
            sa.String(length=10),
            nullable=False,
            comment="Sender category classification (Customer, Agent, System)",
        ),
        sa.Column(
            "sender_user_id",
            sa.UUID(),
            nullable=True,
            comment="Foreign key referencing sender agent user if direction is Outbound",
        ),
        sa.Column(
            "message_type",
            sa.String(length=20),
            server_default="text",
            nullable=False,
            comment="Message content type (text, image, document, audio)",
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
            comment="Message body text or media caption",
        ),
        sa.Column(
            "media_url",
            sa.Text(),
            nullable=True,
            comment="Private object storage path for media attachment",
        ),
        sa.Column(
            "delivery_status",
            sa.String(length=20),
            server_default="Sent",
            nullable=False,
            comment="Delivery lifecycle state (Sent, Delivered, Read, Failed)",
        ),
        sa.Column(
            "metadata",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="Raw JSON webhook or provider response metadata",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation UTC timestamp",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["whatsapp_conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "provider_message_id",
            name="uq_messages_tenant_id_provider_message_id",
        ),
    )
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"], unique=False)
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"], unique=False)
    op.create_index(
        "ix_messages_provider_message_id", "messages", ["provider_message_id"], unique=False
    )
    op.create_index("ix_messages_created_at", "messages", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_provider_message_id", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_index("ix_messages_tenant_id", table_name="messages")
    op.drop_constraint("uq_messages_tenant_id_provider_message_id", "messages", type_="unique")
    op.drop_table("messages")

    op.drop_index("ix_whatsapp_conversations_last_message_at", table_name="whatsapp_conversations")
    op.drop_index("ix_whatsapp_conversations_status", table_name="whatsapp_conversations")
    op.drop_index(
        "ix_whatsapp_conversations_assigned_agent_id", table_name="whatsapp_conversations"
    )
    op.drop_index("ix_whatsapp_conversations_customer_id", table_name="whatsapp_conversations")
    op.drop_index("ix_whatsapp_conversations_tenant_id", table_name="whatsapp_conversations")
    op.drop_constraint(
        "uq_whatsapp_conversations_tenant_id_customer_id",
        "whatsapp_conversations",
        type_="unique",
    )
    op.drop_table("whatsapp_conversations")
