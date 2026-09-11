"""Pydantic Schemas & DTOs for Customer API endpoints (ADR 0008, ADR 0009)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CustomerCreate(BaseModel):
    """Schema for creating a new customer profile."""

    phone: str = Field(
        ...,
        description="Raw or E.164 phone number string",
        examples=["098123456", "+21698123456"],
    )
    full_name: str | None = Field(
        None,
        max_length=100,
        description="Customer display full name",
    )
    first_name: str | None = Field(
        None,
        max_length=50,
        description="Customer first name",
    )
    last_name: str | None = Field(
        None,
        max_length=50,
        description="Customer last name",
    )
    email: str | None = Field(
        None,
        max_length=255,
        description="Customer email address",
    )
    preferred_language: str = Field(
        "fr",
        description="Preferred ISO language code (fr, ar_tn, en)",
    )
    fcr_eligible: bool = Field(
        default=False,
        description="Tunisia FCR privilege eligibility status",
    )
    notes: str | None = Field(
        None,
        description="Agent operational notes on customer",
    )

    @field_validator("preferred_language")
    @classmethod
    def validate_preferred_language(cls, v: str) -> str:
        """Validate preferred language code is among whitelisted ISO options."""
        allowed = ("fr", "ar_tn", "en")
        if v not in allowed:
            raise ValueError(f"Invalid preferred_language '{v}'. Allowed options: {allowed}")
        return v


class CustomerUpdate(BaseModel):
    """Schema for partial updates to a customer profile."""

    full_name: str | None = Field(None, max_length=100)
    first_name: str | None = Field(None, max_length=50)
    last_name: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=255)
    preferred_language: str | None = Field(None)
    fcr_eligible: bool | None = Field(None)
    notes: str | None = Field(None)

    @field_validator("preferred_language")
    @classmethod
    def validate_preferred_language(cls, v: str | None) -> str | None:
        """Validate preferred language code if provided."""
        if v is None:
            return v
        allowed = ("fr", "ar_tn", "en")
        if v not in allowed:
            raise ValueError(f"Invalid preferred_language '{v}'. Allowed options: {allowed}")
        return v


class CustomerResponse(BaseModel):
    """Schema for serializing a customer entity record."""

    id: UUID
    tenant_id: UUID
    phone_e164: str
    whatsapp_id: str | None = None
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    preferred_language: str
    fcr_eligible: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerEnvelope(BaseModel):
    """Standard single-resource API response envelope (ADR 0008)."""

    success: bool = True
    data: CustomerResponse


class CustomerListMeta(BaseModel):
    """Metadata for paginated list endpoints (ADR 0009)."""

    limit: int
    has_next: bool
    next_cursor: str | None = None
    total: int


class CustomerListEnvelope(BaseModel):
    """Standard list-resource API response envelope (ADR 0008, ADR 0009)."""

    success: bool = True
    data: list[CustomerResponse]
    meta: CustomerListMeta
