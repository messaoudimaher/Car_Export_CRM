"""FollowUp Entity Model & Status Enum (WS-14, TASK-1401, docs/domain-model.md)."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.tenant import Tenant
    from app.models.user import User


class FollowUpStatus(StrEnum):
    """Status lifecycle enum for FollowUp tasks."""

    PENDING = "Pending"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class FollowUp(Base):
    """Declarative FollowUp model representing scheduled sales rep tasks."""

    __tablename__ = "follow_ups"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Pending', 'Completed', 'Cancelled')",
            name="ck_follow_ups_status",
        ),
        Index("ix_follow_ups_tenant_id", "tenant_id"),
        Index("ix_follow_ups_lead_id", "lead_id"),
        Index("ix_follow_ups_assigned_user_id", "assigned_user_id"),
        Index("ix_follow_ups_due_at", "due_at"),
        Index("ix_follow_ups_status", "status"),
        Index("ix_follow_ups_tenant_status", "tenant_id", "status"),
        Index("ix_follow_ups_tenant_lead", "tenant_id", "lead_id"),
        Index("ix_follow_ups_due_scan", "tenant_id", "due_at", "status", "reminder_sent"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key referencing parent tenant organization",
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key referencing associated sales lead card",
    )

    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing assigned sales representative user",
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Short actionable follow-up task title string",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed task description or sales note background",
    )

    due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Scheduled task due timestamp (UTC)",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=FollowUpStatus.PENDING.value,
        default=FollowUpStatus.PENDING.value,
        comment="Current task lifecycle status (Pending, Completed, Cancelled)",
    )

    reminder_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        default=False,
        comment="Flag indicating whether reminder notification was emitted by worker",
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when task was marked completed (UTC)",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="follow_ups",
    )

    lead: Mapped["Lead"] = relationship(
        "Lead",
        back_populates="follow_ups",
    )

    assigned_user: Mapped["User | None"] = relationship(
        "User",
    )

    def __init__(self, **kw: Any) -> None:
        """Initialize FollowUp entity setting default in-memory attribute states."""
        kw.setdefault("status", FollowUpStatus.PENDING.value)
        kw.setdefault("reminder_sent", False)
        super().__init__(**kw)

    def mark_completed(self, completion_time: datetime | None = None) -> None:
        """Mark follow-up task as Completed set completed_at timestamp."""
        self.status = FollowUpStatus.COMPLETED.value
        self.completed_at = completion_time or datetime.now(UTC)

    def mark_cancelled(self) -> None:
        """Mark follow-up task as Cancelled."""
        self.status = FollowUpStatus.CANCELLED.value
