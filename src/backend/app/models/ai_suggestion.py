"""AISuggestion Entity Model (WS-12, ADR 0012, docs/ai-architecture.md Section 6.6)."""

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ai_understanding import AIUnderstanding
    from app.models.conversation import WhatsAppConversation
    from app.models.customer import Customer
    from app.models.tenant import Tenant


class AISuggestionStatus(StrEnum):
    """Lifecycle state for AI response suggestions."""

    SUGGESTED_NOT_SENT = "Suggested_Not_Sent"
    ACCEPTED = "Accepted"
    EDITED_AND_SENT = "Edited_And_Sent"
    REJECTED = "Rejected"


class AISuggestion(Base):
    """Declarative model storing provisional sales rep reply drafts (ADR 0012)."""

    __tablename__ = "ai_suggestions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Suggested_Not_Sent', 'Accepted', 'Edited_And_Sent', 'Rejected')",
            name="ck_ai_suggestions_status",
        ),
        Index("ix_ai_suggestions_tenant_id", "tenant_id"),
        Index("ix_ai_suggestions_conversation_id", "conversation_id"),
        Index("ix_ai_suggestions_customer_id", "customer_id"),
        Index("ix_ai_suggestions_understanding_id", "understanding_id"),
        Index("ix_ai_suggestions_status", "status"),
        Index("ix_ai_suggestions_created_at", "created_at"),
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
        comment="Foreign key referencing target conversation thread",
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing target customer profile",
    )

    understanding_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_understandings.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing parent AI understanding extraction",
    )

    suggested_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Draft response text generated for sales representative pre-fill",
    )

    target_language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="fr",
        default="fr",
        comment="Target customer language code (fr, en, ar, derja)",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=AISuggestionStatus.SUGGESTED_NOT_SENT.value,
        default=AISuggestionStatus.SUGGESTED_NOT_SENT.value,
        comment="Lifecycle state (Suggested_Not_Sent, Accepted, Edited_And_Sent, Rejected)",
    )

    model_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="gpt-4o-mini",
        default="gpt-4o-mini",
        comment="LLM provider model identifier used for suggestion",
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
        back_populates="ai_suggestions",
    )

    conversation: Mapped["WhatsAppConversation"] = relationship(
        "WhatsAppConversation",
    )

    customer: Mapped["Customer | None"] = relationship(
        "Customer",
    )

    understanding: Mapped["AIUnderstanding | None"] = relationship(
        "AIUnderstanding",
    )

    def __init__(self, **kw: object) -> None:
        """Initialize AISuggestion entity setting default in-memory values."""
        kw.setdefault("status", AISuggestionStatus.SUGGESTED_NOT_SENT.value)
        kw.setdefault("target_language", "fr")
        kw.setdefault("model_name", "gpt-4o-mini")
        kw.setdefault("prompt_version", "v1.0")
        super().__init__(**kw)
