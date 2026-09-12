"""Vehicle Catalog Entity Model & VAT Regime classification (WS-09, BR-005)."""

import uuid
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.quotation import Quotation
    from app.models.tenant import Tenant


class VATRegime(StrEnum):
    """European VAT Tax Regime classification enum (BR-005)."""

    NETTO_EXPORT = "Netto_Export"
    BRUTTO_MARGIN = "Brutto_Margin"


class VehicleStatus(StrEnum):
    """Vehicle stock inventory status enum."""

    AVAILABLE = "Available"
    RESERVED = "Reserved"
    SOLD = "Sold"
    ARCHIVED = "Archived"


class Vehicle(Base):
    """Declarative Vehicle model representing sourced car stock inventory."""

    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint(
            "vat_regime IN ('Netto_Export', 'Brutto_Margin')",
            name="ck_vehicles_vat_regime",
        ),
        CheckConstraint(
            "status IN ('Available', 'Reserved', 'Sold', 'Archived')",
            name="ck_vehicles_status",
        ),
        Index("ix_vehicles_tenant_id", "tenant_id"),
        Index("ix_vehicles_make_model", "make", "model"),
        Index("ix_vehicles_tenant_status", "tenant_id", "status"),
        Index("ix_vehicles_vin", "vin"),
        Index("ix_vehicles_created_at", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key referencing parent tenant organization",
    )

    vin: Mapped[str | None] = mapped_column(
        String(17),
        nullable=True,
        comment="Vehicle Identification Number (17-char standard chassis VIN)",
    )

    make: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Vehicle manufacturer brand (e.g. Volkswagen, Audi, BMW)",
    )

    model: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Vehicle model name (e.g. Golf 8, A4, X5)",
    )

    first_registration_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="First registration year for FCR 5-year compliance check",
    )

    mileage_km: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Vehicle odometer mileage in kilometers",
    )

    fuel_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Engine fuel classification (Diesel, Petrol, Hybrid, Electric)",
    )

    transmission: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Gearbox transmission type (Automatic, Manual)",
    )

    purchase_price_eur: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Supplier purchase/cost price in Euros (exact decimal)",
    )

    vat_regime: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=VATRegime.NETTO_EXPORT.value,
        server_default="Netto_Export",
        comment="European VAT regime (Netto_Export or Brutto_Margin) (BR-005)",
    )

    supplier_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="European dealership or supplier source name",
    )

    supplier_location: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="European supplier location (e.g. Munich, Germany)",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=VehicleStatus.AVAILABLE.value,
        server_default="Available",
        comment="Stock inventory status (Available, Reserved, Sold, Archived)",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="vehicles",
    )

    quotations: Mapped[list["Quotation"]] = relationship(
        "Quotation",
        back_populates="vehicle",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize Vehicle entity setting default in-memory attribute states."""
        kw.setdefault("vat_regime", VATRegime.NETTO_EXPORT.value)
        kw.setdefault("status", VehicleStatus.AVAILABLE.value)
        super().__init__(**kw)
