"""Tenant Entity Model adhering to ADR 0005 & multi-tenant isolation rules."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ai_suggestion import AISuggestion
    from app.models.ai_understanding import AIUnderstanding
    from app.models.conversation import WhatsAppConversation
    from app.models.customer import Customer
    from app.models.document import Document
    from app.models.inbound_message import InboundMessage
    from app.models.lead import Lead
    from app.models.message import Message
    from app.models.quotation import Quotation
    from app.models.user import User
    from app.models.vehicle import Vehicle
    from app.models.vehicle_request import VehicleRequest
    from app.models.whatsapp_account import WhatsAppAccount


class Tenant(Base):
    """Declarative Tenant model representing an isolated organizational account."""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Organization or company business name",
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        comment="URL-friendly unique tenant identifier slug",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Active tenant status flag",
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    customers: Mapped[list["Customer"]] = relationship(
        "Customer",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    whatsapp_accounts: Mapped[list["WhatsAppAccount"]] = relationship(
        "WhatsAppAccount",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    inbound_messages: Mapped[list["InboundMessage"]] = relationship(
        "InboundMessage",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    conversations: Mapped[list["WhatsAppConversation"]] = relationship(
        "WhatsAppConversation",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    vehicle_requests: Mapped[list["VehicleRequest"]] = relationship(
        "VehicleRequest",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    leads: Mapped[list["Lead"]] = relationship(
        "Lead",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    vehicles: Mapped[list["Vehicle"]] = relationship(
        "Vehicle",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    quotations: Mapped[list["Quotation"]] = relationship(
        "Quotation",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    ai_understandings: Mapped[list["AIUnderstanding"]] = relationship(
        "AIUnderstanding",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    ai_suggestions: Mapped[list["AISuggestion"]] = relationship(
        "AISuggestion",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize Tenant entity setting default in-memory attribute states."""
        kw.setdefault("is_active", True)
        super().__init__(**kw)
