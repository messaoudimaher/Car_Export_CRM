"""Live AI Extraction & Suggestion API Endpoints (ADR 0012, ADR 0014, BR-009)."""

from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, get_current_user, get_llm_provider
from app.ports.llm import LLMCompletionRequest, LLMProvider

router = APIRouter(prefix="/ai", tags=["AI Operations"])


class AIExtractRequest(BaseModel):
    message: str = Field(..., min_length=2, description="Customer WhatsApp message text")


class AIExtractResponse(BaseModel):
    raw_output: str
    parsed: dict[str, Any] | None = None
    model: str
    latency_ms: float
    total_tokens: int


class AISuggestRequest(BaseModel):
    message: str = Field(..., min_length=2, description="Customer inquiry text")
    customer_name: str | None = Field(None, description="Customer name")
    target_vehicle: str | None = Field(None, description="Vehicle identified")


class AISuggestResponse(BaseModel):
    suggested_reply: str
    reasoning: str
    confidence_score: float
    model: str
    latency_ms: float


@router.post("/extract", response_model=AIExtractResponse, status_code=status.HTTP_200_OK)
async def extract_vehicle_specs(
    payload: AIExtractRequest,
    llm: LLMProvider = Depends(get_llm_provider),
    current_user: CurrentUser = Depends(get_current_user),
) -> AIExtractResponse:
    """Extract intent, vehicle specifications, and FCR regime info using live LLM provider."""
    import json

    req = LLMCompletionRequest(
        prompt=(
            f"Customer WhatsApp Message:\n<untrusted_user_message>\n{payload.message}\n</untrusted_user_message>\n\n"
            "Extract in strict JSON format: make, model, year, fuel_type, fcr_eligible (boolean), budget_eur, language, summary_fr."
        ),
        system_prompt="You are an expert automotive CRM assistant for Europe to Tunisia car export. Return ONLY valid JSON.",
        temperature=0.2,
    )
    res = await llm.generate_text(req)

    # Attempt JSON parse
    parsed_json: dict[str, Any] | None = None
    try:
        cleaned = res.content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        parsed_json = json.loads(cleaned.strip())
    except Exception:
        pass

    return AIExtractResponse(
        raw_output=res.content,
        parsed=parsed_json,
        model=res.model,
        latency_ms=res.latency_ms,
        total_tokens=res.total_tokens,
    )


@router.post("/suggest", response_model=AISuggestResponse, status_code=status.HTTP_200_OK)
async def generate_draft_reply(
    payload: AISuggestRequest,
    llm: LLMProvider = Depends(get_llm_provider),
    current_user: CurrentUser = Depends(get_current_user),
) -> AISuggestResponse:
    """Generate professional Human-In-The-Loop WhatsApp response suggestion using live LLM."""
    req = LLMCompletionRequest(
        prompt=(
            f"Customer: {payload.customer_name or 'Client'}\n"
            f"Vehicle context: {payload.target_vehicle or 'Non spécifié'}\n"
            f"Customer message:\n<untrusted_user_message>\n{payload.message}\n</untrusted_user_message>\n\n"
            "Generate a polite, professional, and clear WhatsApp draft response in French proposing next steps (customs simulation, quote PDF, FCR eligibility)."
        ),
        system_prompt="You are a senior sales advisor for a B2B car export company between Europe and Tunisia. Keep reply concise, friendly, and conversion-focused.",
        temperature=0.4,
    )
    res = await llm.generate_text(req)

    return AISuggestResponse(
        suggested_reply=res.content.strip(),
        reasoning="Analyse de la demande client et formulation d'une proposition commerciale adaptée avec régime fiscal.",
        confidence_score=0.92,
        model=res.model,
        latency_ms=res.latency_ms,
    )
