"""Customer Entity Model adhering to ADR 0005, BR-001, BR-014 & database specs."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.conversation import WhatsAppConversation
    from app.models.tenant import Tenant
    from app.models.vehicle_request import VehicleRequest


class Customer(Base):
    """Declarative Customer model representing a buyer master profile."""

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "phone_e164",
            name="uq_customers_tenant_id_phone_e164",
        ),
        Index("ix_customers_tenant_id", "tenant_id"),
        Index("ix_customers_phone_e164", "phone_e164"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key referencing parent tenant organization",
    )

    phone_e164: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="E.164 normalized phone number (e.g. +21698123456)",
    )

    whatsapp_id: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="Raw Meta WhatsApp identifier (wa_id)",
    )

    full_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Customer display full name",
    )

    first_name: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Customer first name",
    )

    last_name: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Customer last name",
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Customer email address",
    )

    preferred_language: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        server_default="fr",
        default="fr",
        comment="Preferred ISO language code (fr, ar_tn, en)",
    )

    fcr_eligible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
        comment="Tunisia FCR privilege eligibility indicator",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Agent operational notes on customer",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="customers",
    )

    conversations: Mapped[list["WhatsAppConversation"]] = relationship(
        "WhatsAppConversation",
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    vehicle_requests: Mapped[list["VehicleRequest"]] = relationship(
        "VehicleRequest",
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize Customer entity setting default in-memory attribute states."""
        kw.setdefault("preferred_language", "fr")
        kw.setdefault("fcr_eligible", False)
        super().__init__(**kw)
