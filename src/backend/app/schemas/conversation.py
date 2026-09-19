"""Pydantic Schemas & DTOs for Conversation & Message API endpoints (ADR 0008, ADR 0009)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationAssignRequest(BaseModel):
    """Schema for claiming or reassigning a conversation thread (FR-INBOX-002)."""

    agent_id: UUID | None = Field(
        None,
        description="Target sales representative user UUID or None to unassign",
    )


class ConversationResponse(BaseModel):
    """Schema for serializing a WhatsAppConversation entity record."""

    id: UUID
    tenant_id: UUID
    customer_id: UUID
    assigned_agent_id: UUID | None = None
    status: str
    mode: str | None = "AI"
    conversation_state: str | None = "AI_ACTIVE"
    handoff_reason: str | None = None
    handoff_summary: str | None = None
    draft_data: dict[str, Any] | None = None
    last_message_at: datetime
    unread_count: int
    created_at: datetime
    updated_at: datetime

    # Enriched presentation fields
    customer_name: str | None = None
    customer_phone_e164: str | None = None
    last_message_content: str | None = None
    active_ai_understanding: dict[str, Any] | None = None
    active_ai_suggestion: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class ConversationEnvelope(BaseModel):
    """Standard single-conversation API response envelope (ADR 0008)."""

    success: bool = True
    data: ConversationResponse


class ConversationListMeta(BaseModel):
    """Metadata for paginated conversation list endpoints (ADR 0009)."""

    limit: int
    has_next: bool
    next_cursor: str | None = None
    total: int


class ConversationListEnvelope(BaseModel):
    """Standard list-conversations API response envelope (ADR 0008, ADR 0009)."""

    success: bool = True
    data: list[ConversationResponse]
    meta: ConversationListMeta


class MessageCreateRequest(BaseModel):
    """Schema for dispatching an outbound WhatsApp message (FR-MSG-001)."""

    content: str = Field(..., min_length=1, description="Message body text or media caption")
    message_type: str = Field("text", description="Type of message content (text, image, etc.)")
    media_url: str | None = Field(None, description="Optional attachment URL")


class MessageResponse(BaseModel):
    """Schema for serializing a Message entity record."""

    id: UUID
    tenant_id: UUID
    conversation_id: UUID
    provider_message_id: str | None = None
    direction: str
    sender_type: str
    sender_user_id: UUID | None = None
    message_type: str
    content: str
    media_url: str | None = None
    delivery_status: str
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_payload")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MessageEnvelope(BaseModel):
    """Standard single-message API response envelope (ADR 0008)."""

    success: bool = True
    data: MessageResponse


class MessageListMeta(BaseModel):
    """Metadata for paginated chat history timeline endpoints (ADR 0009)."""

    limit: int
    has_next: bool
    next_cursor: str | None = None
    total: int


class MessageListEnvelope(BaseModel):
    """Standard message-timeline API response envelope (ADR 0008, ADR 0009)."""

    success: bool = True
    data: list[MessageResponse]
    meta: MessageListMeta
