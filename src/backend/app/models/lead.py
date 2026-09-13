"""Lead Entity Model & Pipeline State Machine definitions (WS-08, BR-011, BR-012)."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.document import Document
    from app.models.followup import FollowUp
    from app.models.quotation import Quotation
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.vehicle_request import VehicleRequest


class LeadStatus(StrEnum):
    """Pipeline stage status enum for Lead entities (BR-011)."""

    NEW = "New"
    QUALIFIED = "Qualified"
    SOURCING = "Sourcing"
    QUOTED = "Quoted"
    WON = "Won"
    LOST = "Lost"


class LeadPriority(StrEnum):
    """Priority level classification enum for Lead entities."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"


class LostReason(StrEnum):
    """Enumerated reasons for lost sales opportunities."""

    OUT_OF_BUDGET = "Out of Budget"
    BOUGHT_LOCALLY = "Bought Locally"
    UNRESPONSIVE = "Unresponsive"
    FCR_INELIGIBLE = "FCR Ineligible"
    OTHER = "Other"


# Allowed state transitions catalog (BR-011 & BR-012)
VALID_STAGE_TRANSITIONS: dict[LeadStatus, set[LeadStatus]] = {
    LeadStatus.NEW: {LeadStatus.QUALIFIED, LeadStatus.LOST},
    LeadStatus.QUALIFIED: {LeadStatus.SOURCING, LeadStatus.LOST},
    LeadStatus.SOURCING: {LeadStatus.QUOTED, LeadStatus.LOST},
    LeadStatus.QUOTED: {LeadStatus.WON, LeadStatus.LOST},
    LeadStatus.LOST: {LeadStatus.NEW},  # Auto-reopen within 90 days (BR-012)
    LeadStatus.WON: set(),  # Terminal state
}


class Lead(Base):
    """Declarative Lead model representing a sales opportunity pipeline card."""

    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_tenant_id", "tenant_id"),
        Index("ix_leads_customer_id", "customer_id"),
        Index("ix_leads_tenant_status", "tenant_id", "status"),
        Index("ix_leads_assigned_agent_id", "assigned_agent_id"),
        Index("ix_leads_created_at", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key referencing parent tenant organization",
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key referencing buyer customer profile",
    )

    vehicle_request_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("vehicle_requests.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing confirmed vehicle specs request",
    )

    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing assigned sales representative",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="New",
        default="New",
        comment="Pipeline stage status (New, Qualified, Sourcing, Quoted, Won, Lost)",
    )

    priority: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="Medium",
        default="Medium",
        comment="Lead priority classification (Low, Medium, High, Urgent)",
    )

    lost_reason: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Categorized reason string if lead status is Lost",
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when lead was closed (Won or Lost)",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="leads",
    )

    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="leads",
    )

    vehicle_request: Mapped["VehicleRequest | None"] = relationship(
        "VehicleRequest",
        back_populates="leads",
    )

    assigned_agent: Mapped["User | None"] = relationship(
        "User",
        back_populates="assigned_leads",
    )

    quotations: Mapped[list["Quotation"]] = relationship(
        "Quotation",
        back_populates="lead",
        cascade="all, delete-orphan",
    )

    follow_ups: Mapped[list["FollowUp"]] = relationship(
        "FollowUp",
        back_populates="lead",
        cascade="all, delete-orphan",
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="lead",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize Lead entity setting default in-memory attribute states."""
        kw.setdefault("status", LeadStatus.NEW.value)
        kw.setdefault("priority", LeadPriority.MEDIUM.value)
        super().__init__(**kw)

    def is_eligible_for_reopen(self, reference_time: datetime | None = None) -> bool:
        """Check if a Lost lead is within the 90-day auto-reopen window (BR-012).

        Args:
            reference_time: Optional timestamp for comparison (defaults to current UTC time).

        Returns:
            bool: True if status is Lost and closed_at is within 90 days, False otherwise.
        """
        if self.status != LeadStatus.LOST.value or self.closed_at is None:
            return False

        now = reference_time or datetime.now(UTC)
        elapsed_days = (now - self.closed_at).days
        return elapsed_days <= 90
