"""Create vehicles table.

Revision ID: 20260912_0007
Revises: 20260912_0006
Create Date: 2026-09-12 02:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260912_0007"
down_revision: str | None = "20260912_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
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
            "vin",
            sa.String(length=17),
            nullable=True,
            comment="Vehicle Identification Number (17-char standard chassis VIN)",
        ),
        sa.Column(
            "make",
            sa.String(length=50),
            nullable=False,
            comment="Vehicle manufacturer brand (e.g. Volkswagen, Audi, BMW)",
        ),
        sa.Column(
            "model",
            sa.String(length=50),
            nullable=False,
            comment="Vehicle model name (e.g. Golf 8, A4, X5)",
        ),
        sa.Column(
            "first_registration_year",
            sa.Integer(),
            nullable=False,
            comment="First registration year for FCR 5-year compliance check",
        ),
        sa.Column(
            "mileage_km",
            sa.Integer(),
            nullable=False,
            comment="Vehicle odometer mileage in kilometers",
        ),
        sa.Column(
            "fuel_type",
            sa.String(length=20),
            nullable=False,
            comment="Engine fuel classification (Diesel, Petrol, Hybrid, Electric)",
        ),
        sa.Column(
            "transmission",
            sa.String(length=20),
            nullable=False,
            comment="Gearbox transmission type (Automatic, Manual)",
        ),
        sa.Column(
            "purchase_price_eur",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            comment="Supplier purchase/cost price in Euros (exact decimal)",
        ),
        sa.Column(
            "vat_regime",
            sa.String(length=20),
            server_default="Netto_Export",
            nullable=False,
            comment="European VAT regime (Netto_Export or Brutto_Margin) (BR-005)",
        ),
        sa.Column(
            "supplier_name",
            sa.String(length=100),
            nullable=True,
            comment="European dealership or supplier source name",
        ),
        sa.Column(
            "supplier_location",
            sa.String(length=100),
            nullable=True,
            comment="European supplier location (e.g. Munich, Germany)",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="Available",
            nullable=False,
            comment="Stock inventory status (Available, Reserved, Sold, Archived)",
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
            name="ck_vehicles_vat_regime",
        ),
        sa.CheckConstraint(
            "status IN ('Available', 'Reserved', 'Sold', 'Archived')",
            name="ck_vehicles_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vehicles_tenant_id", "vehicles", ["tenant_id"], unique=False)
    op.create_index(
        "ix_vehicles_make_model",
        "vehicles",
        ["make", "model"],
        unique=False,
    )
    op.create_index(
        "ix_vehicles_tenant_status",
        "vehicles",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index("ix_vehicles_vin", "vehicles", ["vin"], unique=False)
    op.create_index("ix_vehicles_created_at", "vehicles", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_vehicles_created_at", table_name="vehicles")
    op.drop_index("ix_vehicles_vin", table_name="vehicles")
    op.drop_index("ix_vehicles_tenant_status", table_name="vehicles")
    op.drop_index("ix_vehicles_make_model", table_name="vehicles")
    op.drop_index("ix_vehicles_tenant_id", table_name="vehicles")
    op.drop_table("vehicles")
