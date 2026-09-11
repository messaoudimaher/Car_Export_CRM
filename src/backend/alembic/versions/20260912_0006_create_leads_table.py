"""Create leads table.

Revision ID: 20260912_0006
Revises: 20260912_0005
Create Date: 2026-09-12 01:53:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260912_0006"
down_revision: str | None = "20260912_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leads",
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
            "vehicle_request_id",
            sa.UUID(),
            nullable=True,
            comment="Foreign key referencing confirmed vehicle specs request",
        ),
        sa.Column(
            "assigned_agent_id",
            sa.UUID(),
            nullable=True,
            comment="Foreign key referencing assigned sales representative",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="New",
            nullable=False,
            comment="Pipeline stage status (New, Qualified, Sourcing, Quoted, Won, Lost)",
        ),
        sa.Column(
            "priority",
            sa.String(length=10),
            server_default="Medium",
            nullable=False,
            comment="Lead priority classification (Low, Medium, High, Urgent)",
        ),
        sa.Column(
            "lost_reason",
            sa.String(length=50),
            nullable=True,
            comment="Categorized reason string if lead status is Lost",
        ),
        sa.Column(
            "closed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when lead was closed (Won or Lost)",
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
        sa.ForeignKeyConstraint(
            ["vehicle_request_id"], ["vehicle_requests.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["assigned_agent_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_tenant_id", "leads", ["tenant_id"], unique=False)
    op.create_index("ix_leads_customer_id", "leads", ["customer_id"], unique=False)
    op.create_index(
        "ix_leads_tenant_status",
        "leads",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_leads_assigned_agent_id",
        "leads",
        ["assigned_agent_id"],
        unique=False,
    )
    op.create_index("ix_leads_created_at", "leads", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_leads_created_at", table_name="leads")
    op.drop_index("ix_leads_assigned_agent_id", table_name="leads")
    op.drop_index("ix_leads_tenant_status", table_name="leads")
    op.drop_index("ix_leads_customer_id", table_name="leads")
    op.drop_index("ix_leads_tenant_id", table_name="leads")
    op.drop_table("leads")
