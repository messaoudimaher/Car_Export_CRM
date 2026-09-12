"""Pydantic DTO Schemas for AI Response Suggestions (WS-12, ADR 0012)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.ai_suggestion import AISuggestionStatus


class AISuggestionCreate(BaseModel):
    """Input payload schema for persisting an AI response suggestion draft."""

    tenant_id: uuid.UUID = Field(..., description="Tenant organization UUID")
    conversation_id: uuid.UUID = Field(..., description="WhatsApp conversation UUID")
    customer_id: uuid.UUID | None = Field(default=None, description="Target customer UUID")
    understanding_id: uuid.UUID | None = Field(
        default=None, description="Associated AI understanding UUID"
    )
    suggested_text: str = Field(..., description="Draft response suggestion text")
    target_language: str = Field(default="fr", description="Target customer language code")
    status: str = Field(
        default=AISuggestionStatus.SUGGESTED_NOT_SENT.value,
        description="Lifecycle state (Suggested_Not_Sent, Accepted, Edited_And_Sent, Rejected)",
    )
    model_name: str = Field(default="gpt-4o-mini", description="LLM provider model string")
    prompt_version: str = Field(default="v1.0", description="System prompt version")


class AISuggestionUpdateStatus(BaseModel):
    """Payload schema for updating AI suggestion status."""

    status: AISuggestionStatus = Field(..., description="Target status transition")


class AISuggestionRead(BaseModel):
    """Response schema for returning an AI suggestion record."""

    id: uuid.UUID = Field(..., description="Unique UUIDv7 identifier")
    tenant_id: uuid.UUID = Field(..., description="Tenant organization UUID")
    conversation_id: uuid.UUID = Field(..., description="Target conversation UUID")
    customer_id: uuid.UUID | None = Field(default=None, description="Target customer UUID")
    understanding_id: uuid.UUID | None = Field(
        default=None, description="Associated AI understanding UUID"
    )
    suggested_text: str = Field(..., description="Suggested draft reply text")
    target_language: str = Field(..., description="Target language code")
    status: str = Field(
        ...,
        description="Status (Suggested_Not_Sent, Accepted, Edited_And_Sent, Rejected)",
    )
    model_name: str = Field(..., description="LLM model string")
    prompt_version: str = Field(..., description="Prompt version string")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")

    model_config = ConfigDict(from_attributes=True)
