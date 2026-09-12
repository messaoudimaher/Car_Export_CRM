"""VehicleRequest Pydantic Schemas & Response Envelopes (ADR 0008, BR-004)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class VehicleRequestCreate(BaseModel):
    """Payload schema for creating a new vehicle request."""

    customer_id: uuid.UUID = Field(..., description="Target buyer customer UUID")
    make: str = Field(..., max_length=50, description="Vehicle manufacturer brand")
    model: str = Field(..., max_length=50, description="Vehicle model name")
    min_year: int | None = Field(None, ge=1900, le=2100, description="Minimum manufacture year")
    max_year: int | None = Field(None, ge=1900, le=2100, description="Maximum manufacture year")
    fuel_type: str | None = Field(
        None, max_length=20, description="Engine fuel type (Diesel, Petrol, Hybrid, Electric)"
    )
    transmission: str | None = Field(
        None, max_length=20, description="Transmission type (Automatic, Manual)"
    )
    max_mileage_km: int | None = Field(None, ge=0, description="Maximum odometer mileage in km")
    budget_eur: Decimal | None = Field(None, ge=0, description="Maximum budget in EUR")
    destination_port: str = Field("Rades", max_length=50, description="Tunisia destination port")


class VehicleRequestResponse(BaseModel):
    """Schema representing a confirmed or provisional VehicleRequest entity."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    make: str
    model: str
    min_year: int | None = None
    max_year: int | None = None
    fuel_type: str | None = None
    transmission: str | None = None
    max_mileage_km: int | None = None
    budget_eur: Decimal | None = None
    fcr_compatible: bool
    destination_port: str
    status: str
    is_human_validated: bool
    confirmed_by_user_id: uuid.UUID | None = None
    confirmed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VehicleRequestEnvelope(BaseModel):
    """RFC 7807 compatible envelope for single VehicleRequest response."""

    success: bool = True
    data: VehicleRequestResponse


class VehicleRequestListMeta(BaseModel):
    """Cursor pagination metadata for VehicleRequest list endpoints."""

    limit: int
    has_next: bool
    next_cursor: str | None = None
    total: int


class VehicleRequestListEnvelope(BaseModel):
    """Envelope for paginated list of VehicleRequests."""

    success: bool = True
    data: list[VehicleRequestResponse]
    meta: VehicleRequestListMeta
