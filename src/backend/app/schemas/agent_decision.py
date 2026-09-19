"""Structured Agent Decision Schema for Gemini Autonomous Sales Agent (Phase 3)."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator


class AgentIntent(str, Enum):
    """Normalized customer conversation intents."""

    GREETING = "GREETING"
    FAQ = "FAQ"
    VEHICLE_REQUEST = "VEHICLE_REQUEST"
    REQUEST_UPDATE = "REQUEST_UPDATE"
    CONFIRMATION = "CONFIRMATION"
    REJECTION = "REJECTION"
    HUMAN_REQUEST = "HUMAN_REQUEST"
    COMPLAINT = "COMPLAINT"
    PRICE_REQUEST = "PRICE_REQUEST"
    OTHER = "OTHER"


class AgentDecision(BaseModel):
    """Single-pass structured agent reasoning output validated strictly against Pydantic schema."""

    intent: str = Field(
        default="OTHER",
        description="Intent classification: GREETING, FAQ, VEHICLE_REQUEST, REQUEST_UPDATE, CONFIRMATION, REJECTION, HUMAN_REQUEST, COMPLAINT, PRICE_REQUEST, OTHER",
    )
    language: str = Field(
        default="fr",
        description="Detected customer language/dialect: ar, fr, en, de, derja, mixed",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Understanding confidence score from 0.0 to 1.0",
    )
    make: str | None = Field(
        default=None,
        description="Extracted vehicle manufacturer (e.g. BMW, Volkswagen, Audi, Mercedes-Benz)",
    )
    model: str | None = Field(
        default=None,
        description="Extracted vehicle model name (e.g. X5, Golf 8, A4, C200)",
    )
    year: int | None = Field(
        default=None,
        description="Target vehicle production year (between 2010 and 2027)",
    )
    fuel_type: str | None = Field(
        default=None,
        description="Fuel classification: Diesel, Petrol, Hybrid, Electric",
    )
    transmission: str | None = Field(
        default=None,
        description="Gearbox: Automatic, Manual",
    )
    color: str | None = Field(
        default=None,
        description="Vehicle color preference",
    )
    budget_eur: float | None = Field(
        default=None,
        description="Customer budget in Euros",
    )
    max_mileage_km: int | None = Field(
        default=None,
        description="Maximum odometer mileage in kilometers",
    )
    destination_port: str | None = Field(
        default=None,
        description="Tunisia destination port (Rades, La Goulette, Bizerte, Zarzis)",
    )
    fcr_eligible: bool | None = Field(
        default=None,
        description="Whether customer mentioned FCR tax-exemption eligibility",
    )
    additional_requirements: str | None = Field(
        default=None,
        description="Any specific customer requirements, options, or packages",
    )
    customer_confirmation_required: bool = Field(
        default=False,
        description="Set to true if all required vehicle criteria are gathered and summary is presented for confirmation",
    )
    customer_confirmed: bool = Field(
        default=False,
        description="Set to true if customer explicitly confirmed the summarized vehicle request",
    )
    human_attention_required: bool = Field(
        default=False,
        description="Set to true if customer asked for human, complaint, or unsupported question requires human attention",
    )
    human_attention_reason: str | None = Field(
        default=None,
        description="Reason code if human attention is required",
    )
    response_text: str = Field(
        ...,
        description="Exact conversational WhatsApp reply message in customer's language/dialect to be sent automatically",
    )
    reasoning: str | None = Field(
        default=None,
        description="Short technical reasoning for decision",
    )

    @field_validator("make", mode="before")
    @classmethod
    def clean_make(cls, v: Any) -> str | None:
        if isinstance(v, str):
            v = v.strip()
            if not v or v.lower() in ("null", "none", "unknown", "n/a", "non spécifié"):
                return None
            if v.upper() in ("BMW", "VW", "BYD", "MG", "GMC", "SUV", "AMG"):
                return v.upper()
            return v.title()
        return None

    @field_validator("model", mode="before")
    @classmethod
    def clean_model(cls, v: Any) -> str | None:
        if isinstance(v, str):
            v = v.strip()
            return v if v and v.lower() not in ("null", "none", "unknown", "n/a") else None
        return None
