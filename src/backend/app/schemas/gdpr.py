"""Pydantic DTO schemas for GDPR Data Erasure & Anonymization Engine (WS-15, TASK-1503)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GDPRAnonymizeRequest(BaseModel):
    """Input payload for customer PII right-to-erasure anonymization request."""

    reason: str = Field(
        default="GDPR Right to Erasure Request",
        min_length=1,
        max_length=255,
        description="Justification or ticket reference for anonymization",
    )


class GDPRAnonymizeResponse(BaseModel):
    """Response payload returned upon completing customer PII anonymization."""

    model_config = ConfigDict(from_attributes=True)

    customer_id: UUID = Field(description="Customer UUID identifier")
    tenant_id: UUID = Field(description="Parent tenant organization UUID")
    is_anonymized: bool = Field(description="Anonymization completion indicator")
    anonymized_at: datetime = Field(description="UTC timestamp when anonymization was executed")
    documents_purged_count: int = Field(description="Number of customer export documents purged")
    message: str = Field(description="Human-readable execution summary message")


class GDPRLegalHoldRequest(BaseModel):
    """Input payload for setting or removing legal retention hold status."""

    legal_hold: bool = Field(..., description="True to enforce legal hold, False to release")
