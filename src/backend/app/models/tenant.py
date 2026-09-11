"""Tenant Entity Model adhering to ADR 0005 & multi-tenant isolation rules."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.conversation import WhatsAppConversation
    from app.models.customer import Customer
    from app.models.inbound_message import InboundMessage
    from app.models.message import Message
    from app.models.user import User
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

    def __init__(self, **kw: object) -> None:
        """Initialize Tenant entity setting default in-memory attribute states."""
        kw.setdefault("is_active", True)
        super().__init__(**kw)
