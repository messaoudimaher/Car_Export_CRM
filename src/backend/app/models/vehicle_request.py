"""VehicleRequest Entity Model (WS-08, BR-004, docs/database-design.md Section 5.7)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.lead import Lead
    from app.models.tenant import Tenant
    from app.models.user import User


def check_fcr_compliance(
    min_year: int | None = None,
    max_year: int | None = None,
    reference_year: int | None = None,
) -> bool:
    """Check if vehicle year parameters satisfy Tunisia 5-year FCR age limit rule (BR-004).

    Tunisia FCR privilege permits importing passenger cars that are 5 years old or less
    at registration. If requested vehicle manufacture year is older than (current_year - 5),
    the request is NOT FCR compliant.

    Args:
        min_year: Minimum vehicle manufacture year.
        max_year: Maximum vehicle manufacture year.
        reference_year: Optional reference year for calculation (defaults to current UTC year).

    Returns:
        bool: True if vehicle age <= 5 years, False if age > 5 years.
    """
    current_year = reference_year or datetime.now(UTC).year
    min_allowed_year = current_year - 5

    if max_year is not None and max_year < min_allowed_year:
        return False
    if min_year is not None and min_year < min_allowed_year:
        return False
    return True


class VehicleRequest(Base):
    """Declarative VehicleRequest model storing buyer vehicle sourcing specs & FCR compliance."""

    __tablename__ = "vehicle_requests"
    __table_args__ = (
        Index("ix_vehicle_requests_tenant_id", "tenant_id"),
        Index("ix_vehicle_requests_customer_id", "customer_id"),
        Index("ix_vehicle_requests_make_model", "make", "model"),
        Index("ix_vehicle_requests_created_at", "created_at"),
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

    min_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Minimum acceptable manufacture year",
    )

    max_year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum acceptable manufacture year",
    )

    fuel_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Engine fuel classification (Diesel, Petrol, Hybrid, Electric)",
    )

    transmission: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Gearbox transmission type (Automatic, Manual)",
    )

    max_mileage_km: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum odometer mileage limit in kilometers",
    )

    budget_eur: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Maximum sourcing budget stated in Euros",
    )

    fcr_compatible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
        comment="Indicates spec compliance with 5-year FCR age limit (BR-004)",
    )

    destination_port: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="Rades",
        default="Rades",
        comment="Destination seaport in Tunisia (Rades, La Goulette, Bizerte)",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="Pending",
        default="Pending",
        comment="Vehicle request status (Pending, Sourcing, Quoted, Fulfilled, Cancelled)",
    )

    is_human_validated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
        comment="HITL human verification flag for AI-extracted requests",
    )

    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing sales rep who confirmed requirements",
    )

    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when requirements were human validated",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="vehicle_requests",
    )

    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="vehicle_requests",
    )

    confirmed_by_user: Mapped["User | None"] = relationship(
        "User",
    )

    leads: Mapped[list["Lead"]] = relationship(
        "Lead",
        back_populates="vehicle_request",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize VehicleRequest entity auto-calculating FCR age compliance (BR-004)."""
        kw.setdefault("destination_port", "Rades")
        kw.setdefault("status", "Pending")
        kw.setdefault("is_human_validated", False)

        min_year_val = kw.get("min_year")
        max_year_val = kw.get("max_year")
        if "fcr_compatible" not in kw:
            min_yr = int(str(min_year_val)) if min_year_val is not None else None
            max_yr = int(str(max_year_val)) if max_year_val is not None else None
            is_compliant = check_fcr_compliance(
                min_year=min_yr,
                max_year=max_yr,
            )
            kw["fcr_compatible"] = is_compliant

        super().__init__(**kw)
