"""AIUnderstanding Entity Model (WS-12, ADR 0007, docs/database-design.md Section 5.6)."""

import uuid
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.conversation import WhatsAppConversation
    from app.models.customer import Customer
    from app.models.message import Message
    from app.models.tenant import Tenant


class AIUnderstandingStatus(StrEnum):
    """Provisional LLM extraction lifecycle status."""

    PROVISIONAL = "Provisional"
    CONFIRMED = "Confirmed"
    REJECTED = "Rejected"


class AIUnderstandingIntent(StrEnum):
    """Customer intent classification categories."""

    SOURCING_INQUIRY = "SOURCING_INQUIRY"
    PRICE_CHECK = "PRICE_CHECK"
    FCR_CUSTOMS_INQUIRY = "FCR_CUSTOMS_INQUIRY"
    SHIPPING_STATUS = "SHIPPING_STATUS"
    GENERAL_QUESTION = "GENERAL_QUESTION"


class AIUnderstanding(Base):
    """Declarative model storing provisional Layer 2 AI extractions (INV-003)."""

    __tablename__ = "ai_understandings"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0.000 AND confidence_score <= 1.000",
            name="ck_ai_understandings_confidence_score",
        ),
        CheckConstraint(
            "status IN ('Provisional', 'Confirmed', 'Rejected')",
            name="ck_ai_understandings_status",
        ),
        Index("ix_ai_understandings_tenant_id", "tenant_id"),
        Index("ix_ai_understandings_conversation_id", "conversation_id"),
        Index("ix_ai_understandings_message_id", "message_id"),
        Index("ix_ai_understandings_customer_id", "customer_id"),
        Index("ix_ai_understandings_status", "status"),
        Index("ix_ai_understandings_intent", "intent"),
        Index("ix_ai_understandings_created_at", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key referencing parent tenant organization",
    )

    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("whatsapp_conversations.id", ondelete="CASCADE"),
        nullable=True,
        comment="Foreign key referencing parent conversation thread",
    )

    message_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=True,
        comment="Foreign key referencing source customer message",
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing customer profile",
    )

    intent: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=AIUnderstandingIntent.SOURCING_INQUIRY.value,
        default=AIUnderstandingIntent.SOURCING_INQUIRY.value,
        comment="Extracted intent classification (e.g. SOURCING_INQUIRY, FCR_CUSTOMS_INQUIRY)",
    )

    extracted_data_jsonb: Mapped[dict[str, object]] = mapped_column(
        "extracted_payload",
        JSONB,
        nullable=False,
        server_default="{}",
        comment="Schema-validated JSON payload from LLM (AIExtractionResult)",
    )

    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        server_default="0.000",
        default=Decimal("0.000"),
        comment="Model confidence score between 0.000 and 1.000",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=AIUnderstandingStatus.PROVISIONAL.value,
        default=AIUnderstandingStatus.PROVISIONAL.value,
        comment="Provisional extraction state (Provisional, Confirmed, Rejected)",
    )

    detected_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="fr",
        default="fr",
        comment="Detected language code (fr, en, ar, derja)",
    )

    summary_fr: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="",
        default="",
        comment="One-sentence French summary for agent inbox UI",
    )

    model_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="gpt-4o-mini",
        default="gpt-4o-mini",
        comment="LLM provider model identifier used for extraction",
    )

    prompt_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="v1.0",
        default="v1.0",
        comment="System prompt version identifier",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="ai_understandings",
    )

    conversation: Mapped["WhatsAppConversation | None"] = relationship(
        "WhatsAppConversation",
    )

    message: Mapped["Message | None"] = relationship(
        "Message",
    )

    customer: Mapped["Customer | None"] = relationship(
        "Customer",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize AIUnderstanding entity setting default in-memory values."""
        kw.setdefault("intent", AIUnderstandingIntent.SOURCING_INQUIRY.value)
        kw.setdefault("extracted_data_jsonb", {})
        kw.setdefault("confidence_score", Decimal("0.000"))
        kw.setdefault("status", AIUnderstandingStatus.PROVISIONAL.value)
        kw.setdefault("detected_language", "fr")
        kw.setdefault("summary_fr", "")
        kw.setdefault("model_name", "gpt-4o-mini")
        kw.setdefault("prompt_version", "v1.0")
        super().__init__(**kw)
