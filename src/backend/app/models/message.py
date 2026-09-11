"""Message Entity Model (WS-07, docs/database-design.md Section 5.5)."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.conversation import WhatsAppConversation
    from app.models.tenant import Tenant
    from app.models.user import User


class Message(Base):
    """Declarative Message model representing append-only inbound and outbound chat payloads."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider_message_id",
            name="uq_messages_tenant_id_provider_message_id",
        ),
        Index("ix_messages_tenant_id", "tenant_id"),
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_provider_message_id", "provider_message_id"),
        Index("ix_messages_created_at", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key referencing parent tenant organization",
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("whatsapp_conversations.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key referencing parent conversation thread",
    )

    provider_message_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Meta WhatsApp wamid string for deduplication (BR-008)",
    )

    direction: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Message flow direction (Inbound, Outbound)",
    )

    sender_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Sender category classification (Customer, Agent, System)",
    )

    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing sender agent user if direction is Outbound",
    )

    message_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="text",
        default="text",
        comment="Message content type (text, image, document, audio)",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Message body text or media caption",
    )

    media_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Private object storage path for media attachment",
    )

    delivery_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="Sent",
        default="Sent",
        comment="Delivery lifecycle state (Sent, Delivered, Read, Failed)",
    )

    metadata_payload: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Raw JSON webhook or provider response metadata",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="messages",
    )

    conversation: Mapped["WhatsAppConversation"] = relationship(
        "WhatsAppConversation",
        back_populates="messages",
    )

    sender_user: Mapped["User | None"] = relationship(
        "User",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize Message entity setting default values."""
        kw.setdefault("message_type", "text")
        kw.setdefault("delivery_status", "Sent")
        kw.setdefault("metadata_payload", {})
        super().__init__(**kw)
