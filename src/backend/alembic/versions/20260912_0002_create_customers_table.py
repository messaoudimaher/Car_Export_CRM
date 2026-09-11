"""Create customers table with tenant-scoped composite unique index.

Revision ID: 20260912_0002
Revises: 20260911_0001
Create Date: 2026-09-12 00:46:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260912_0002"
down_revision: str | None = "20260911_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create customers table
    op.create_table(
        "customers",
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
            "phone_e164",
            sa.String(length=20),
            nullable=False,
            comment="E.164 normalized phone number (e.g. +21698123456)",
        ),
        sa.Column(
            "whatsapp_id",
            sa.String(length=30),
            nullable=True,
            comment="Raw Meta WhatsApp identifier (wa_id)",
        ),
        sa.Column(
            "full_name",
            sa.String(length=100),
            nullable=True,
            comment="Customer display full name",
        ),
        sa.Column(
            "first_name",
            sa.String(length=50),
            nullable=True,
            comment="Customer first name",
        ),
        sa.Column(
            "last_name",
            sa.String(length=50),
            nullable=True,
            comment="Customer last name",
        ),
        sa.Column(
            "email",
            sa.String(length=255),
            nullable=True,
            comment="Customer email address",
        ),
        sa.Column(
            "preferred_language",
            sa.String(length=5),
            server_default="fr",
            nullable=False,
            comment="Preferred ISO language code (fr, ar_tn, en)",
        ),
        sa.Column(
            "fcr_eligible",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="Tunisia FCR privilege eligibility indicator",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="Agent operational notes on customer",
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
        sa.UniqueConstraint(
            "tenant_id",
            "phone_e164",
            name="uq_customers_tenant_id_phone_e164",
        ),
    )
    op.create_index("ix_customers_tenant_id", "customers", ["tenant_id"], unique=False)
    op.create_index("ix_customers_phone_e164", "customers", ["phone_e164"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_customers_phone_e164", table_name="customers")
    op.drop_index("ix_customers_tenant_id", table_name="customers")
    op.drop_constraint("uq_customers_tenant_id_phone_e164", "customers", type_="unique")
    op.drop_table("customers")
