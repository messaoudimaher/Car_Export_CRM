"""Pydantic DTO contracts for AI Multilingual Parameter & Intent Extraction (BR-009, ADR 0012)."""

from enum import StrEnum

from pydantic import BaseModel, Field


class CustomerIntent(StrEnum):
    """Supported customer message intent classifications (docs/ai-architecture.md Section 6.2)."""

    SOURCING_INQUIRY = "SOURCING_INQUIRY"
    PRICE_CHECK = "PRICE_CHECK"
    FCR_CUSTOMS_INQUIRY = "FCR_CUSTOMS_INQUIRY"
    SHIPPING_STATUS = "SHIPPING_STATUS"
    GENERAL_QUESTION = "GENERAL_QUESTION"


class FuelType(StrEnum):
    """Engine fuel type requirements."""

    DIESEL = "Diesel"
    PETROL = "Petrol"
    HYBRID = "Hybrid"
    ELECTRIC = "Electric"


class TransmissionType(StrEnum):
    """Transmission preference."""

    AUTOMATIC = "Automatic"
    MANUAL = "Manual"


class DestinationPort(StrEnum):
    """Tunisia destination ports."""

    RADES = "Rades"
    LA_GOULETTE = "La Goulette"


class DetectedLanguage(StrEnum):
    """Detected primary customer language."""

    FR = "fr"
    AR_TN = "ar_tn"
    AR = "ar"
    EN = "en"
    MIXED = "mixed"


class AIExtractionResult(BaseModel):
    """Structured output DTO for AI multilingual intent and vehicle parameter extraction."""

    intent: CustomerIntent = Field(
        default=CustomerIntent.SOURCING_INQUIRY,
        description="Extracted primary customer intent classification",
    )
    make: str | None = Field(
        default=None,
        description="Extracted vehicle manufacturer make (e.g. Volkswagen, BMW, Audi, Mercedes)",
    )
    model: str | None = Field(
        default=None,
        description="Extracted vehicle model designation (e.g. Golf 8, Série 3, A4, C-Class)",
    )
    min_year: int | None = Field(
        default=None, ge=2000, le=2030, description="Minimum production year"
    )
    max_year: int | None = Field(
        default=None, ge=2000, le=2030, description="Maximum production year"
    )
    fuel_type: FuelType | None = Field(
        default=None, description="Extracted engine fuel type preference"
    )
    transmission: TransmissionType | None = Field(
        default=None, description="Extracted transmission preference"
    )
    max_mileage_km: int | None = Field(
        default=None, ge=0, description="Maximum odometer mileage limit in kilometers"
    )
    budget_eur: float | None = Field(
        default=None, gt=0.0, description="Extracted maximum purchase budget in EUR"
    )
    fcr_eligible_mentioned: bool | None = Field(
        default=None, description="Whether customer explicitly mentioned FCR tax regime"
    )
    destination_port: DestinationPort | None = Field(
        default=None, description="Extracted destination port in Tunisia"
    )
    detected_language: DetectedLanguage = Field(
        default=DetectedLanguage.FR, description="Primary detected customer message language"
    )
    summary_fr: str = Field(
        default="",
        description="Concise 1-2 sentence French summary of customer inquiry and vehicle specs",
    )
    confidence_score: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description="Heuristic extraction confidence score (0.000 to 1.000)",
    )
