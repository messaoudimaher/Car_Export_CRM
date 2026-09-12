"""Lead Pydantic Schemas & Response Envelopes (ADR 0008, BR-011, BR-012)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.lead import LeadPriority, LeadStatus, LostReason


class LeadCreate(BaseModel):
    """Payload schema for creating a new sales Lead opportunity card."""

    customer_id: uuid.UUID = Field(..., description="Target buyer customer UUID")
    assigned_agent_id: uuid.UUID | None = Field(
        None, description="Optional assigned sales representative UUID"
    )
    vehicle_request_id: uuid.UUID | None = Field(
        None, description="Optional linked vehicle request UUID"
    )
    priority: LeadPriority = Field(
        LeadPriority.MEDIUM, description="Initial lead priority classification"
    )


class LeadStageUpdate(BaseModel):
    """Payload schema for updating a lead status stage or assignment parameters."""

    status: LeadStatus | None = Field(None, description="Target pipeline stage status (BR-011)")
    priority: LeadPriority | None = Field(None, description="Updated lead priority classification")
    assigned_agent_id: uuid.UUID | None = Field(None, description="Updated assigned sales rep UUID")
    vehicle_request_id: uuid.UUID | None = Field(None, description="Linked vehicle request UUID")
    lost_reason: LostReason | str | None = Field(
        None, description="Reason classification if status is transitioned to Lost"
    )


class LeadResponse(BaseModel):
    """Schema representing a Lead sales opportunity card."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    vehicle_request_id: uuid.UUID | None = None
    assigned_agent_id: uuid.UUID | None = None
    status: LeadStatus
    priority: LeadPriority
    lost_reason: str | None = None
    closed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeadEnvelope(BaseModel):
    """RFC 7807 compatible envelope for single Lead response."""

    success: bool = True
    data: LeadResponse


class LeadListMeta(BaseModel):
    """Cursor pagination metadata for Lead list endpoints."""

    limit: int
    has_next: bool
    next_cursor: str | None = None
    total: int


class LeadListEnvelope(BaseModel):
    """Envelope for paginated list of Leads."""

    success: bool = True
    data: list[LeadResponse]
    meta: LeadListMeta
