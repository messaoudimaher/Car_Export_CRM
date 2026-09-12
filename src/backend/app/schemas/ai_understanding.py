"""Pydantic DTO Schemas for AI Understanding persistence layer (WS-12, ADR 0007)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.ai_understanding import AIUnderstandingIntent, AIUnderstandingStatus


class AIUnderstandingCreate(BaseModel):
    """Input payload schema for persisting a provisional AI extraction understanding."""

    tenant_id: uuid.UUID = Field(..., description="Tenant organization UUID")
    conversation_id: uuid.UUID | None = Field(
        default=None, description="WhatsApp conversation UUID"
    )
    message_id: uuid.UUID | None = Field(default=None, description="Source customer message UUID")
    customer_id: uuid.UUID | None = Field(default=None, description="Associated customer UUID")
    intent: str = Field(
        default=AIUnderstandingIntent.SOURCING_INQUIRY.value,
        description="Extracted intent classification string",
    )
    extracted_data_jsonb: dict[str, Any] = Field(
        default_factory=dict,
        description="Schema-validated JSON payload from LLM extraction",
    )
    confidence_score: Decimal = Field(
        default=Decimal("0.000"),
        ge=Decimal("0.000"),
        le=Decimal("1.000"),
        description="Model extraction confidence score (0.000 to 1.000)",
    )
    status: str = Field(
        default=AIUnderstandingStatus.PROVISIONAL.value,
        description="Lifecycle state (Provisional, Confirmed, Rejected)",
    )
    detected_language: str = Field(default="fr", description="Detected language code")
    summary_fr: str = Field(default="", description="One-sentence French summary")
    model_name: str = Field(default="gpt-4o-mini", description="LLM provider model string")
    prompt_version: str = Field(default="v1.0", description="System prompt version")


class AIUnderstandingUpdateStatus(BaseModel):
    """Payload schema for updating AI understanding status (Confirmed, Rejected)."""

    status: AIUnderstandingStatus = Field(..., description="Target status transition")


class AIUnderstandingRead(BaseModel):
    """Response schema for returning an AI understanding record."""

    id: uuid.UUID = Field(..., description="Unique UUIDv7 identifier")
    tenant_id: uuid.UUID = Field(..., description="Tenant organization UUID")
    conversation_id: uuid.UUID | None = Field(
        default=None, description="WhatsApp conversation UUID"
    )
    message_id: uuid.UUID | None = Field(default=None, description="Source customer message UUID")
    customer_id: uuid.UUID | None = Field(default=None, description="Associated customer UUID")
    intent: str = Field(..., description="Extracted intent classification")
    extracted_data_jsonb: dict[str, Any] = Field(
        ..., description="Structured extraction JSON payload"
    )
    confidence_score: Decimal = Field(..., description="Confidence score")
    status: str = Field(..., description="Status (Provisional, Confirmed, Rejected)")
    detected_language: str = Field(..., description="Detected language code")
    summary_fr: str = Field(..., description="One-sentence French summary")
    model_name: str = Field(..., description="LLM model string")
    prompt_version: str = Field(..., description="Prompt version string")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")

    model_config = ConfigDict(from_attributes=True)
