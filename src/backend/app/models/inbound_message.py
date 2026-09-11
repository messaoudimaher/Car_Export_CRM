"""InboundMessage Entity Model (WS-06, BR-008, ADR 0018)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.whatsapp_account import WhatsAppAccount


class InboundMessage(Base):
    """Declarative InboundMessage model for pre-ACK persistence and atomic deduplication."""

    __tablename__ = "inbound_messages"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider_message_id",
            name="uq_inbound_messages_tenant_id_provider_message_id",
        ),
        Index("ix_inbound_messages_tenant_id", "tenant_id"),
        Index("ix_inbound_messages_provider_message_id", "provider_message_id"),
        Index("ix_inbound_messages_sender_phone", "sender_phone_e164"),
        Index("ix_inbound_messages_processed_at", "processed_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key referencing parent tenant organization",
    )

    whatsapp_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("whatsapp_accounts.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing bound WhatsApp account",
    )

    provider_message_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Meta WhatsApp wamid identifier for atomic deduplication (BR-008)",
    )

    sender_phone_e164: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Sender's E.164 normalized phone number",
    )

    message_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="text",
        default="text",
        comment="Payload content type (text, image, document, audio, video)",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Inbound message body text or media caption",
    )

    raw_payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Complete raw JSON webhook event payload",
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when ARQ background worker completed message processing",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="inbound_messages",
    )

    whatsapp_account: Mapped["WhatsAppAccount | None"] = relationship(
        "WhatsAppAccount",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize InboundMessage entity setting defaults."""
        kw.setdefault("message_type", "text")
        kw.setdefault("raw_payload", {})
        super().__init__(**kw)
