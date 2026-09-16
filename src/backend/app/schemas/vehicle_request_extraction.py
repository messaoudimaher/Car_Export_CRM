"""Vehicle Request Extraction schema and backend validation engine (Step 1)."""

from typing import Any
from pydantic import BaseModel, Field, field_validator

ACRONYMS = {"BMW": "BMW", "VW": "VW", "BYD": "BYD", "MG": "MG", "GMC": "GMC", "SUV": "SUV"}


class VehicleRequestExtraction(BaseModel):
    """Schema for customer vehicle sourcing and quotation inquiries."""

    intent: str = Field(
        default="NEW_VEHICLE_REQUEST",
        description="Intent category: NEW_VEHICLE_REQUEST, PRICE_CHECK, FCR_CUSTOMS_INQUIRY, GENERAL_QUESTION",
    )
    make: str | None = Field(
        default=None,
        description="Vehicle manufacturer brand (e.g., Peugeot, Volkswagen, BMW, Audi, Mercedes)",
    )
    model: str | None = Field(
        default=None,
        description="Vehicle model designation (e.g., 208, 3008, Golf 8, X3, C-Class)",
    )
    year: int | None = Field(
        default=None,
        description="Target vehicle production year",
    )
    budget_eur: float | None = Field(
        default=None,
        description="Customer budget in EUR",
    )
    fcr_eligible: bool | None = Field(
        default=None,
        description="Whether customer mentioned FCR tax-exemption eligibility",
    )
    language: str = Field(
        default="mixed",
        description="Detected message language (en, fr, ar_tn, mixed)",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Backend-computed required fields that are missing from customer inquiry",
    )

    @field_validator("make", mode="before")
    @classmethod
    def clean_make(cls, v: Any) -> str | None:
        if isinstance(v, str):
            v = v.strip()
            if not v or v.lower() in ("null", "none", "unknown"):
                return None
            upper = v.upper()
            if upper in ACRONYMS:
                return upper
            return v.capitalize()
        return None

    @field_validator("model", mode="before")
    @classmethod
    def clean_model(cls, v: Any) -> str | None:
        if isinstance(v, str):
            v = v.strip()
            return v if v and v.lower() not in ("null", "none", "unknown") else None
        return None


def validate_vehicle_request(raw_data: dict[str, Any]) -> VehicleRequestExtraction:
    """Backend validation layer: enforce business constraints and compute missing fields.

    The backend (not the LLM) is the single source of truth for business rules:
    - Year must be within realistic bounds (2010 to 2027).
    - Budget must be strictly positive.
    - Determines required fields missing for quotation (make, model, year, budget_eur).
    """
    # 1. Parse and validate through Pydantic
    obj = VehicleRequestExtraction.model_validate(raw_data)

    # 2. Enforce business rules on production year
    if obj.year is not None:
        if obj.year < 2010 or obj.year > 2027:
            obj.year = None

    # 3. Enforce business rules on budget
    if obj.budget_eur is not None and obj.budget_eur <= 0:
        obj.budget_eur = None

    # 4. Compute missing required fields for sourcing quotation
    missing: list[str] = []
    if not obj.make:
        missing.append("make")
    if not obj.model:
        missing.append("model")
    if not obj.year:
        missing.append("year")
    if not obj.budget_eur:
        missing.append("budget_eur")

    obj.missing_fields = missing
    return obj
