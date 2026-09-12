"""Vehicle Pydantic Schemas & Response Envelopes (ADR 0008, BR-005)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.vehicle import VATRegime, VehicleStatus


class VehicleCreate(BaseModel):
    """Payload schema for creating a new vehicle stock record."""

    vin: str | None = Field(
        None, max_length=17, description="Vehicle Chassis VIN Number (17 chars)"
    )
    make: str = Field(..., max_length=50, description="Vehicle manufacturer brand")
    model: str = Field(..., max_length=50, description="Vehicle model name")
    first_registration_year: int = Field(
        ..., ge=1900, le=2100, description="First registration year"
    )
    mileage_km: int = Field(..., ge=0, description="Odometer mileage in km")
    fuel_type: str = Field(
        ...,
        max_length=20,
        description="Engine fuel classification (Diesel, Petrol, Hybrid, Electric)",
    )
    transmission: str = Field(
        ..., max_length=20, description="Transmission type (Automatic, Manual)"
    )
    purchase_price_eur: Decimal = Field(..., ge=0, description="Exact purchase cost price in EUR")
    vat_regime: VATRegime = Field(
        VATRegime.NETTO_EXPORT, description="European VAT tax regime (Netto_Export, Brutto_Margin)"
    )
    supplier_name: str | None = Field(None, max_length=100, description="European dealership name")
    supplier_location: str | None = Field(None, max_length=100, description="Supplier city/country")
    status: VehicleStatus = Field(
        VehicleStatus.AVAILABLE, description="Stock status (Available, Reserved, Sold, Archived)"
    )


class VehicleUpdate(BaseModel):
    """Payload schema for updating vehicle stock attributes."""

    vin: str | None = Field(None, max_length=17)
    make: str | None = Field(None, max_length=50)
    model: str | None = Field(None, max_length=50)
    first_registration_year: int | None = Field(None, ge=1900, le=2100)
    mileage_km: int | None = Field(None, ge=0)
    fuel_type: str | None = Field(None, max_length=20)
    transmission: str | None = Field(None, max_length=20)
    purchase_price_eur: Decimal | None = Field(None, ge=0)
    vat_regime: VATRegime | None = None
    supplier_name: str | None = Field(None, max_length=100)
    supplier_location: str | None = Field(None, max_length=100)
    status: VehicleStatus | None = None


class VehicleResponse(BaseModel):
    """Schema representing a sourced Vehicle entity."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    vin: str | None = None
    make: str
    model: str
    first_registration_year: int
    mileage_km: int
    fuel_type: str
    transmission: str
    purchase_price_eur: Decimal
    vat_regime: VATRegime
    supplier_name: str | None = None
    supplier_location: str | None = None
    status: VehicleStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VehicleEnvelope(BaseModel):
    """RFC 7807 compatible envelope for single Vehicle response."""

    success: bool = True
    data: VehicleResponse


class VehicleListMeta(BaseModel):
    """Cursor pagination metadata for Vehicle list endpoints."""

    limit: int
    has_next: bool
    next_cursor: str | None = None
    total: int


class VehicleListEnvelope(BaseModel):
    """Envelope for paginated list of Vehicles."""

    success: bool = True
    data: list[VehicleResponse]
    meta: VehicleListMeta
