"""Create follow_ups table (WS-14, TASK-1401).

Revision ID: 20260913_0013
Revises: 20260913_0012
Create Date: 2026-09-13 16:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260913_0013"
down_revision: str | None = "20260913_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create follow_ups table with constraints and indexes."""
    op.create_table(
        "follow_ups",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique UUIDv7 identifier",
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
            comment="Foreign key referencing parent tenant organization",
        ),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
            comment="Foreign key referencing associated sales lead card",
        ),
        sa.Column(
            "assigned_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="Foreign key referencing assigned sales representative user",
        ),
        sa.Column(
            "title",
            sa.String(255),
            nullable=False,
            comment="Short actionable follow-up task title string",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Detailed task description or sales note background",
        ),
        sa.Column(
            "due_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Scheduled task due timestamp (UTC)",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="Pending",
            comment="Current task lifecycle status (Pending, Completed, Cancelled)",
        ),
        sa.Column(
            "reminder_sent",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Flag indicating whether reminder notification was emitted by worker",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when task was marked completed (UTC)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Record update timestamp",
        ),
        sa.CheckConstraint(
            "status IN ('Pending', 'Completed', 'Cancelled')",
            name="ck_follow_ups_status",
        ),
    )

    # Indexes
    op.create_index("ix_follow_ups_tenant_id", "follow_ups", ["tenant_id"])
    op.create_index("ix_follow_ups_lead_id", "follow_ups", ["lead_id"])
    op.create_index("ix_follow_ups_assigned_user_id", "follow_ups", ["assigned_user_id"])
    op.create_index("ix_follow_ups_due_at", "follow_ups", ["due_at"])
    op.create_index("ix_follow_ups_status", "follow_ups", ["status"])
    op.create_index("ix_follow_ups_tenant_status", "follow_ups", ["tenant_id", "status"])
    op.create_index("ix_follow_ups_tenant_lead", "follow_ups", ["tenant_id", "lead_id"])
    op.create_index(
        "ix_follow_ups_due_scan",
        "follow_ups",
        ["tenant_id", "due_at", "status", "reminder_sent"],
    )


def downgrade() -> None:
    """Drop follow_ups table."""
    op.drop_table("follow_ups")
