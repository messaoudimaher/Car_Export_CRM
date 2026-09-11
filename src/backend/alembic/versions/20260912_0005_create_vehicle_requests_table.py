"""Create vehicle_requests table.

Revision ID: 20260912_0005
Revises: 20260912_0004
Create Date: 2026-09-12 01:48:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260912_0005"
down_revision: str | None = "20260912_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicle_requests",
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
            "min_year",
            sa.Integer(),
            nullable=True,
            comment="Minimum acceptable manufacture year",
        ),
        sa.Column(
            "max_year",
            sa.Integer(),
            nullable=True,
            comment="Maximum acceptable manufacture year",
        ),
        sa.Column(
            "fuel_type",
            sa.String(length=20),
            nullable=True,
            comment="Engine fuel classification (Diesel, Petrol, Hybrid, Electric)",
        ),
        sa.Column(
            "transmission",
            sa.String(length=20),
            nullable=True,
            comment="Gearbox transmission type (Automatic, Manual)",
        ),
        sa.Column(
            "max_mileage_km",
            sa.Integer(),
            nullable=True,
            comment="Maximum odometer mileage limit in kilometers",
        ),
        sa.Column(
            "budget_eur",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
            comment="Maximum sourcing budget stated in Euros",
        ),
        sa.Column(
            "fcr_compatible",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="Indicates spec compliance with 5-year FCR age limit (BR-004)",
        ),
        sa.Column(
            "destination_port",
            sa.String(length=50),
            server_default="Rades",
            nullable=False,
            comment="Destination seaport in Tunisia (Rades, La Goulette, Bizerte)",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="Pending",
            nullable=False,
            comment="Vehicle request status (Pending, Sourcing, Quoted, Fulfilled, Cancelled)",
        ),
        sa.Column(
            "is_human_validated",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="HITL human verification flag for AI-extracted requests",
        ),
        sa.Column(
            "confirmed_by_user_id",
            sa.UUID(),
            nullable=True,
            comment="Foreign key referencing sales rep who confirmed requirements",
        ),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when requirements were human validated",
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
        sa.ForeignKeyConstraint(["confirmed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_vehicle_requests_tenant_id",
        "vehicle_requests",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_vehicle_requests_customer_id",
        "vehicle_requests",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_vehicle_requests_make_model",
        "vehicle_requests",
        ["make", "model"],
        unique=False,
    )
    op.create_index(
        "ix_vehicle_requests_created_at",
        "vehicle_requests",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vehicle_requests_created_at", table_name="vehicle_requests")
    op.drop_index("ix_vehicle_requests_make_model", table_name="vehicle_requests")
    op.drop_index("ix_vehicle_requests_customer_id", table_name="vehicle_requests")
    op.drop_index("ix_vehicle_requests_tenant_id", table_name="vehicle_requests")
    op.drop_table("vehicle_requests")
