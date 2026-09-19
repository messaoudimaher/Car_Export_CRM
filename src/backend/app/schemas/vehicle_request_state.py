"""Vehicle Request Domain Criteria & State Validation Schema (Phase 1 Domain Foundation)."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, Field, field_validator

ACRONYMS = {"BMW": "BMW", "VW": "VW", "BYD": "BYD", "MG": "MG", "GMC": "GMC", "SUV": "SUV", "AMG": "AMG"}
DEFAULT_REQUIRED_FIELDS = ["make", "model", "year", "budget_eur"]


class VehicleRequestCriteria(BaseModel):
    """Normalized vehicle sourcing criteria model validated deterministically by backend."""

    make: str | None = Field(default=None, description="Vehicle brand manufacturer")
    model: str | None = Field(default=None, description="Vehicle model name")
    year: int | None = Field(default=None, description="Manufacture year")
    min_year: int | None = Field(default=None, description="Minimum acceptable year")
    max_year: int | None = Field(default=None, description="Maximum acceptable year")
    fuel_type: str | None = Field(default=None, description="Fuel category (Diesel, Petrol, Hybrid, Electric)")
    transmission: str | None = Field(default=None, description="Gearbox (Automatic, Manual)")
    color: str | None = Field(default=None, description="Vehicle exterior/interior color")
    max_mileage_km: int | None = Field(default=None, description="Maximum acceptable odometer mileage")
    budget_eur: float | None = Field(default=None, description="Budget in EUR")
    destination_port: str = Field(default="Rades", description="Tunisia port of entry")
    fcr_eligible: bool = Field(default=False, description="Tunisia FCR tax exemption status")
    additional_requirements: str | None = Field(default=None, description="Custom options or specifications")

    @field_validator("make", mode="before")
    @classmethod
    def clean_make(cls, v: Any) -> str | None:
        if isinstance(v, str):
            v = v.strip()
            if not v or v.lower() in ("null", "none", "unknown", "non spécifié", "n/a"):
                return None
            upper = v.upper()
            if upper in ACRONYMS:
                return upper
            return v.title()
        return None

    @field_validator("model", mode="before")
    @classmethod
    def clean_model(cls, v: Any) -> str | None:
        if isinstance(v, str):
            v = v.strip()
            return v if v and v.lower() not in ("null", "none", "unknown", "n/a") else None
        return None

    @field_validator("fuel_type", mode="before")
    @classmethod
    def clean_fuel(cls, v: Any) -> str | None:
        if isinstance(v, str):
            v_low = v.strip().lower()
            if "diesel" in v_low or "mazout" in v_low or "dci" in v_low or "tdi" in v_low:
                return "Diesel"
            if "essence" in v_low or "petrol" in v_low or "benzin" in v_low or "gasoline" in v_low:
                return "Petrol"
            if "hybride" in v_low or "hybrid" in v_low:
                return "Hybrid"
            if "electrique" in v_low or "electric" in v_low or "ev" in v_low:
                return "Electric"
            return v.strip().title()
        return None

    @field_validator("transmission", mode="before")
    @classmethod
    def clean_transmission(cls, v: Any) -> str | None:
        if isinstance(v, str):
            v_low = v.strip().lower()
            if "auto" in v_low or "bva" in v_low or "dsg" in v_low or "steptronic" in v_low:
                return "Automatic"
            if "manuelle" in v_low or "manual" in v_low or "bvm" in v_low or "manuell" in v_low:
                return "Manual"
            return v.strip().title()
        return None


class ValidatedVehicleRequestState(BaseModel):
    """Complete validated state for vehicle request with computed missing fields and qualification status."""

    criteria: VehicleRequestCriteria
    missing_fields: list[str] = Field(default_factory=list)
    is_complete: bool = Field(default=False)
    fcr_compliant: bool = Field(default=True)


def validate_vehicle_criteria(
    raw_data: dict[str, Any],
    required_fields: list[str] | None = None,
    current_year: int | None = None,
) -> ValidatedVehicleRequestState:
    """Backend deterministic validation engine for vehicle sourcing criteria.

    - Normalizes input parameters.
    - Sanitizes invalid years and negative budgets.
    - Calculates missing fields based on company required fields.
    - Evaluates 5-year FCR age compliance.
    """
    cleaned_data = {k: v for k, v in raw_data.items() if v is not None and v != ""}
    
    # Year bounds checking
    yr = cleaned_data.get("year")
    if yr is not None:
        try:
            yr_int = int(yr)
            if 2010 <= yr_int <= 2027:
                cleaned_data["year"] = yr_int
            else:
                cleaned_data["year"] = None
        except (ValueError, TypeError):
            cleaned_data["year"] = None

    # Budget checking
    bg = cleaned_data.get("budget_eur")
    if bg is not None:
        try:
            bg_float = float(bg)
            if bg_float > 0:
                cleaned_data["budget_eur"] = bg_float
            else:
                cleaned_data["budget_eur"] = None
        except (ValueError, TypeError):
            cleaned_data["budget_eur"] = None

    criteria = VehicleRequestCriteria.model_validate(cleaned_data)

    target_required = required_fields if required_fields is not None else DEFAULT_REQUIRED_FIELDS
    missing: list[str] = []

    criteria_dict = criteria.model_dump()
    for field in target_required:
        val = criteria_dict.get(field)
        if val is None or val == "":
            missing.append(field)

    # FCR compliance check (5 years max age)
    curr_yr = current_year or datetime.now(UTC).year
    min_allowed_fcr_year = curr_yr - 5
    fcr_compliant = True
    if criteria.year is not None and criteria.year < min_allowed_fcr_year:
        fcr_compliant = False

    is_complete = len(missing) == 0

    return ValidatedVehicleRequestState(
        criteria=criteria,
        missing_fields=missing,
        is_complete=is_complete,
        fcr_compliant=fcr_compliant,
    )
