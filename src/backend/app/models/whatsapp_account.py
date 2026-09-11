"""WhatsAppAccount Entity Model (WS-06, BR-008, ADR 0018)."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class WhatsAppAccount(Base):
    """Declarative WhatsAppAccount model binding phone_number_id to tenant organization."""

    __tablename__ = "whatsapp_accounts"
    __table_args__ = (
        UniqueConstraint(
            "phone_number_id",
            name="uq_whatsapp_accounts_phone_number_id",
        ),
        Index("ix_whatsapp_accounts_tenant_id", "tenant_id"),
        Index("ix_whatsapp_accounts_phone_number_id", "phone_number_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key referencing parent tenant organization",
    )

    phone_number_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Meta WhatsApp Cloud API Phone Number ID",
    )

    display_phone_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="Human-readable display phone number",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="Active",
        default="Active",
        comment="Account operational status (Active, Suspended, Inactive)",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="whatsapp_accounts",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize WhatsAppAccount entity setting default values."""
        kw.setdefault("status", "Active")
        super().__init__(**kw)
