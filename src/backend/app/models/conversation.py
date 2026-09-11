"""WhatsAppConversation Entity Model (WS-07, docs/database-design.md Section 5.4)."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.message import Message
    from app.models.tenant import Tenant
    from app.models.user import User


class WhatsAppConversation(Base):
    """Declarative WhatsAppConversation model representing operational chat thread context."""

    __tablename__ = "whatsapp_conversations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "customer_id",
            name="uq_whatsapp_conversations_tenant_id_customer_id",
        ),
        Index("ix_whatsapp_conversations_tenant_id", "tenant_id"),
        Index("ix_whatsapp_conversations_customer_id", "customer_id"),
        Index("ix_whatsapp_conversations_assigned_agent_id", "assigned_agent_id"),
        Index("ix_whatsapp_conversations_status", "status"),
        Index("ix_whatsapp_conversations_last_message_at", "last_message_at"),
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

    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing assigned sales representative user",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="PendingAgent",
        default="PendingAgent",
        comment="Conversation thread operational status (PendingAgent, Active, Resolved, Archived)",
    )

    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        comment="Timestamp of most recent inbound/outbound message dispatch",
    )

    unread_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        default=0,
        comment="Count of unread inbound messages for assigned agent",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="conversations",
    )

    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="conversations",
    )

    assigned_agent: Mapped["User | None"] = relationship(
        "User",
        back_populates="assigned_conversations",
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at.asc()",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize WhatsAppConversation entity setting default values."""
        kw.setdefault("status", "PendingAgent")
        kw.setdefault("unread_count", 0)
        kw.setdefault("last_message_at", datetime.now(UTC))
        super().__init__(**kw)
