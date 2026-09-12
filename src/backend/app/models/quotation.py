"""Quotation & QuotationItem Entity Models with cent pricing (WS-10, BR-005, BR-006, BR-015)."""

import uuid
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.vehicle import VATRegime

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.tenant import Tenant
    from app.models.vehicle import Vehicle


class QuotationStatus(StrEnum):
    """Lifecycle status enum for Quotation entities."""

    DRAFT = "Draft"
    PENDING_APPROVAL = "Pending_Approval"
    APPROVED = "Approved"
    SENT = "Sent"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    EXPIRED = "Expired"


class QuotationApprovalStatus(StrEnum):
    """Approval status enum for manager discount/margin overrides (BR-015)."""

    AUTO_APPROVED = "Auto_Approved"
    PENDING_APPROVAL = "Pending_Approval"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class Quotation(Base):
    """Declarative Quotation model representing commercial export price offers."""

    __tablename__ = "quotations"
    __table_args__ = (
        CheckConstraint(
            "vat_regime IN ('Netto_Export', 'Brutto_Margin')",
            name="ck_quotations_vat_regime",
        ),
        CheckConstraint(
            "status IN ("
            "'Draft', 'Pending_Approval', 'Approved', 'Sent', 'Accepted', 'Rejected', 'Expired'"
            ")",
            name="ck_quotations_status",
        ),
        CheckConstraint(
            "approval_status IN ('Auto_Approved', 'Pending_Approval', 'Approved', 'Rejected')",
            name="ck_quotations_approval_status",
        ),
        Index("ix_quotations_tenant_id", "tenant_id"),
        Index("ix_quotations_lead_id", "lead_id"),
        Index("ix_quotations_vehicle_id", "vehicle_id"),
        Index("ix_quotations_tenant_status", "tenant_id", "status"),
        Index("ix_quotations_quote_number", "quote_number"),
        Index("ix_quotations_created_at", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key referencing parent tenant organization",
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key referencing target sales lead opportunity",
    )

    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing target vehicle in catalog",
    )

    quote_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Unique commercial quotation tracking reference code (e.g. QT-2026-00001)",
    )

    vat_regime: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=VATRegime.NETTO_EXPORT.value,
        server_default="Netto_Export",
        comment="European VAT Tax Regime classification (Netto_Export/Brutto_Margin) (BR-005)",
    )

    vehicle_price_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Base vehicle price in Euro cents (integer cents for exact pricing)",
    )

    shipping_fee_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="Transport and logistics shipping fee in Euro cents",
    )

    customs_estimate_tnd: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        default=Decimal("0.000"),
        server_default="0.000",
        comment="Estimated Tunisian customs duties in TND (BR-006 informational estimate)",
    )

    discount_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="Custom discount applied in Euro cents",
    )

    discount_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
        comment="Discount percentage (e.g. 5.00 for 5% discount) (BR-015)",
    )

    total_price_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Calculated total quote price in Euro cents (vehicle + shipping - discount)",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=QuotationStatus.DRAFT.value,
        server_default="Draft",
        comment="Quotation lifecycle status (Draft, Pending_Approval, Approved, Sent, etc.)",
    )

    approval_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=QuotationApprovalStatus.AUTO_APPROVED.value,
        server_default="Auto_Approved",
        comment="Manager approval status (Auto_Approved, Pending_Approval, Approved) (BR-015)",
    )

    disclaimer_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Mandatory customs estimate disclaimer text (BR-006)",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Sales representative internal quote notes",
    )

    pdf_s3_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="S3 object key for generated quote PDF document",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="quotations",
    )

    lead: Mapped["Lead"] = relationship(
        "Lead",
        back_populates="quotations",
    )

    vehicle: Mapped["Vehicle | None"] = relationship(
        "Vehicle",
        back_populates="quotations",
    )

    items: Mapped[list["QuotationItem"]] = relationship(
        "QuotationItem",
        back_populates="quotation",
        cascade="all, delete-orphan",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize Quotation entity setting default in-memory attribute states."""
        kw.setdefault("vat_regime", VATRegime.NETTO_EXPORT.value)
        kw.setdefault("status", QuotationStatus.DRAFT.value)
        kw.setdefault("approval_status", QuotationApprovalStatus.AUTO_APPROVED.value)
        kw.setdefault("shipping_fee_cents", 0)
        kw.setdefault("discount_cents", 0)
        kw.setdefault("discount_percentage", Decimal("0.00"))
        kw.setdefault("customs_estimate_tnd", Decimal("0.000"))
        super().__init__(**kw)


class QuotationItem(Base):
    """Declarative QuotationItem model representing additional fee line items in a quote."""

    __tablename__ = "quotation_items"
    __table_args__ = (
        Index("ix_quotation_items_quotation_id", "quotation_id"),
        Index("ix_quotation_items_created_at", "created_at"),
    )

    quotation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("quotations.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key referencing parent quotation",
    )

    description: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Line item description (e.g. Export preparation fee, Homologation document)",
    )

    unit_price_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Unit price in Euro cents",
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="Item quantity count",
    )

    total_price_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Total line item price in Euro cents (unit_price_cents * quantity)",
    )

    # Relationship
    quotation: Mapped["Quotation"] = relationship(
        "Quotation",
        back_populates="items",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize QuotationItem entity setting default attribute states."""
        kw.setdefault("quantity", 1)
        super().__init__(**kw)
