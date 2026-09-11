"""Create whatsapp_accounts and inbound_messages tables.

Revision ID: 20260912_0003
Revises: 20260912_0002
Create Date: 2026-09-12 01:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "20260912_0003"
down_revision: str | None = "20260912_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create whatsapp_accounts table
    op.create_table(
        "whatsapp_accounts",
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
            "phone_number_id",
            sa.String(length=50),
            nullable=False,
            comment="Meta WhatsApp Cloud API Phone Number ID",
        ),
        sa.Column(
            "display_phone_number",
            sa.String(length=30),
            nullable=True,
            comment="Human-readable display phone number",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="Active",
            nullable=False,
            comment="Account operational status (Active, Suspended, Inactive)",
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone_number_id", name="uq_whatsapp_accounts_phone_number_id"),
    )
    op.create_index(
        "ix_whatsapp_accounts_tenant_id", "whatsapp_accounts", ["tenant_id"], unique=False
    )
    op.create_index(
        "ix_whatsapp_accounts_phone_number_id",
        "whatsapp_accounts",
        ["phone_number_id"],
        unique=True,
    )

    # Create inbound_messages table
    op.create_table(
        "inbound_messages",
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
            "whatsapp_account_id",
            sa.UUID(),
            nullable=True,
            comment="Foreign key referencing bound WhatsApp account",
        ),
        sa.Column(
            "provider_message_id",
            sa.String(length=100),
            nullable=False,
            comment="Meta WhatsApp wamid identifier for atomic deduplication (BR-008)",
        ),
        sa.Column(
            "sender_phone_e164",
            sa.String(length=20),
            nullable=False,
            comment="Sender's E.164 normalized phone number",
        ),
        sa.Column(
            "message_type",
            sa.String(length=20),
            server_default="text",
            nullable=False,
            comment="Payload content type (text, image, document, audio, video)",
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
            comment="Inbound message body text or media caption",
        ),
        sa.Column(
            "raw_payload",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="Complete raw JSON webhook event payload",
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when ARQ background worker completed message processing",
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
        sa.ForeignKeyConstraint(
            ["whatsapp_account_id"], ["whatsapp_accounts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "provider_message_id",
            name="uq_inbound_messages_tenant_id_provider_message_id",
        ),
    )
    op.create_index(
        "ix_inbound_messages_tenant_id", "inbound_messages", ["tenant_id"], unique=False
    )
    op.create_index(
        "ix_inbound_messages_provider_message_id",
        "inbound_messages",
        ["provider_message_id"],
        unique=False,
    )
    op.create_index(
        "ix_inbound_messages_sender_phone",
        "inbound_messages",
        ["sender_phone_e164"],
        unique=False,
    )
    op.create_index(
        "ix_inbound_messages_processed_at",
        "inbound_messages",
        ["processed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_inbound_messages_processed_at", table_name="inbound_messages")
    op.drop_index("ix_inbound_messages_sender_phone", table_name="inbound_messages")
    op.drop_index("ix_inbound_messages_provider_message_id", table_name="inbound_messages")
    op.drop_index("ix_inbound_messages_tenant_id", table_name="inbound_messages")
    op.drop_constraint(
        "uq_inbound_messages_tenant_id_provider_message_id",
        "inbound_messages",
        type_="unique",
    )
    op.drop_table("inbound_messages")

    op.drop_index("ix_whatsapp_accounts_phone_number_id", table_name="whatsapp_accounts")
    op.drop_index("ix_whatsapp_accounts_tenant_id", table_name="whatsapp_accounts")
    op.drop_constraint("uq_whatsapp_accounts_phone_number_id", "whatsapp_accounts", type_="unique")
    op.drop_table("whatsapp_accounts")
