"""Create quotations and quotation_items tables.

Revision ID: 20260912_0008
Revises: 20260912_0007
Create Date: 2026-09-12 02:16:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260912_0008"
down_revision: str | None = "20260912_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create quotations table
    op.create_table(
        "quotations",
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
            "lead_id",
            sa.UUID(),
            nullable=False,
            comment="Foreign key referencing target sales lead opportunity",
        ),
        sa.Column(
            "vehicle_id",
            sa.UUID(),
            nullable=True,
            comment="Foreign key referencing target vehicle in catalog",
        ),
        sa.Column(
            "quote_number",
            sa.String(length=50),
            nullable=False,
            comment="Unique commercial quotation tracking reference code (e.g. QT-2026-00001)",
        ),
        sa.Column(
            "vat_regime",
            sa.String(length=20),
            server_default="Netto_Export",
            nullable=False,
            comment="European VAT Tax Regime classification (Netto_Export/Brutto_Margin) (BR-005)",
        ),
        sa.Column(
            "vehicle_price_cents",
            sa.BigInteger(),
            nullable=False,
            comment="Base vehicle price in Euro cents (integer cents for exact pricing)",
        ),
        sa.Column(
            "shipping_fee_cents",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
            comment="Transport and logistics shipping fee in Euro cents",
        ),
        sa.Column(
            "customs_estimate_tnd",
            sa.Numeric(precision=12, scale=3),
            server_default="0.000",
            nullable=False,
            comment="Estimated Tunisian customs duties in TND (BR-006 informational estimate)",
        ),
        sa.Column(
            "discount_cents",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
            comment="Custom discount applied in Euro cents",
        ),
        sa.Column(
            "discount_percentage",
            sa.Numeric(precision=5, scale=2),
            server_default="0.00",
            nullable=False,
            comment="Discount percentage (e.g. 5.00 for 5% discount) (BR-015)",
        ),
        sa.Column(
            "total_price_cents",
            sa.BigInteger(),
            nullable=False,
            comment="Calculated total quote price in Euro cents (vehicle + shipping - discount)",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="Draft",
            nullable=False,
            comment="Quotation lifecycle status (Draft, Pending_Approval, Approved, Sent, etc.)",
        ),
        sa.Column(
            "approval_status",
            sa.String(length=20),
            server_default="Auto_Approved",
            nullable=False,
            comment="Manager approval status (Auto_Approved, Pending_Approval, Approved) (BR-015)",
        ),
        sa.Column(
            "disclaimer_text",
            sa.Text(),
            nullable=True,
            comment="Mandatory customs estimate disclaimer text (BR-006)",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="Sales representative internal quote notes",
        ),
        sa.Column(
            "pdf_s3_key",
            sa.String(length=255),
            nullable=True,
            comment="S3 object key for generated quote PDF document",
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
            "vat_regime IN ('Netto_Export', 'Brutto_Margin')",
            name="ck_quotations_vat_regime",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'Draft', 'Pending_Approval', 'Approved', 'Sent', 'Accepted', 'Rejected', 'Expired'"
            ")",
            name="ck_quotations_status",
        ),
        sa.CheckConstraint(
            "approval_status IN ('Auto_Approved', 'Pending_Approval', 'Approved', 'Rejected')",
            name="ck_quotations_approval_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quotations_tenant_id", "quotations", ["tenant_id"], unique=False)
    op.create_index("ix_quotations_lead_id", "quotations", ["lead_id"], unique=False)
    op.create_index("ix_quotations_vehicle_id", "quotations", ["vehicle_id"], unique=False)
    op.create_index(
        "ix_quotations_tenant_status", "quotations", ["tenant_id", "status"], unique=False
    )
    op.create_index("ix_quotations_quote_number", "quotations", ["quote_number"], unique=False)
    op.create_index("ix_quotations_created_at", "quotations", ["created_at"], unique=False)

    # 2. Create quotation_items table
    op.create_table(
        "quotation_items",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            comment="Time-ordered UUIDv7 primary key (ADR 0005)",
        ),
        sa.Column(
            "quotation_id",
            sa.UUID(),
            nullable=False,
            comment="Foreign key referencing parent quotation",
        ),
        sa.Column(
            "description",
            sa.String(length=255),
            nullable=False,
            comment="Line item description (e.g. Export preparation fee, Homologation document)",
        ),
        sa.Column(
            "unit_price_cents",
            sa.BigInteger(),
            nullable=False,
            comment="Unit price in Euro cents",
        ),
        sa.Column(
            "quantity",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="Item quantity count",
        ),
        sa.Column(
            "total_price_cents",
            sa.BigInteger(),
            nullable=False,
            comment="Total line item price in Euro cents (unit_price_cents * quantity)",
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
        sa.ForeignKeyConstraint(["quotation_id"], ["quotations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_quotation_items_quotation_id", "quotation_items", ["quotation_id"], unique=False
    )
    op.create_index(
        "ix_quotation_items_created_at", "quotation_items", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_quotation_items_created_at", table_name="quotation_items")
    op.drop_index("ix_quotation_items_quotation_id", table_name="quotation_items")
    op.drop_table("quotation_items")

    op.drop_index("ix_quotations_created_at", table_name="quotations")
    op.drop_index("ix_quotations_quote_number", table_name="quotations")
    op.drop_index("ix_quotations_tenant_status", table_name="quotations")
    op.drop_index("ix_quotations_vehicle_id", table_name="quotations")
    op.drop_index("ix_quotations_lead_id", table_name="quotations")
    op.drop_index("ix_quotations_tenant_id", table_name="quotations")
    op.drop_table("quotations")
