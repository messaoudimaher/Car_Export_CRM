"""Automated Test Suite for Step 1 (Extraction), Step 2 (FAQ Grounding), and Step 3 (Agent Policy)."""

import pytest
from app.adapters.llm_gemini import GeminiAdapter
from app.core.agent_policy import AgentBehaviorPolicy, AgentMode, load_agent_policy
from app.ports.llm import LLMCompletionRequest
from app.schemas.vehicle_request_extraction import VehicleRequestExtraction, validate_vehicle_request
from app.services.faq_service import FAQService


@pytest.fixture
def gemini_adapter() -> GeminiAdapter:
    return GeminiAdapter()


@pytest.fixture
def faq_service(gemini_adapter: GeminiAdapter) -> FAQService:
    return FAQService(gemini_adapter)


# ============================================================================
# STEP 1: MULTILINGUAL STRUCTURED EXTRACTION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_step1_extraction_mixed_arabic_french(gemini_adapter: GeminiAdapter) -> None:
    """Step 1: Test Mixed Arabic/French prompt: 'نحب Peugeot 208 موديل 2022 بميزانية 15000 يورو.'"""
    message = "نحب Peugeot 208 موديل 2022 بميزانية 15000 يورو."
    req = LLMCompletionRequest(
        prompt=(
            f"Extract vehicle inquiry specs from customer message:\n<untrusted_user_message>\n{message}\n</untrusted_user_message>\n\n"
            "Return JSON matching: intent, make, model, year, budget_eur, language, fcr_eligible."
        ),
        model="gemini-3.6-flash",
    )
    validated_raw, _ = await gemini_adapter.generate_structured_output(req, VehicleRequestExtraction)
    
    # Backend validation layer enforces business rules and computes missing fields
    final_validated = validate_vehicle_request(validated_raw.model_dump())

    assert final_validated.make == "Peugeot"
    assert final_validated.model == "208"
    assert final_validated.year == 2022
    assert final_validated.budget_eur == 15000
    assert final_validated.missing_fields == []


@pytest.mark.asyncio
async def test_step1_extraction_french(gemini_adapter: GeminiAdapter) -> None:
    """Step 1: Test French prompt."""
    message = "Bonjour, je cherche une Volkswagen Golf 8 de 2021 avec un budget max de 22000 euros."
    req = LLMCompletionRequest(
        prompt=f"Customer message:\n<untrusted_user_message>\n{message}\n</untrusted_user_message>",
        model="gemini-3.6-flash",
    )
    validated_raw, _ = await gemini_adapter.generate_structured_output(req, VehicleRequestExtraction)
    final_validated = validate_vehicle_request(validated_raw.model_dump())

    assert final_validated.make == "Volkswagen"
    assert "Golf" in (final_validated.model or "")
    assert final_validated.year == 2021
    assert final_validated.budget_eur == 22000
    assert final_validated.missing_fields == []


@pytest.mark.asyncio
async def test_step1_extraction_english(gemini_adapter: GeminiAdapter) -> None:
    """Step 1: Test English prompt with missing budget."""
    message = "Hello, I would like to import a 2023 BMW X5 to Tunisia."
    req = LLMCompletionRequest(
        prompt=f"Customer message:\n<untrusted_user_message>\n{message}\n</untrusted_user_message>",
        model="gemini-3.6-flash",
    )
    validated_raw, _ = await gemini_adapter.generate_structured_output(req, VehicleRequestExtraction)
    final_validated = validate_vehicle_request(validated_raw.model_dump())

    assert final_validated.make == "BMW"
    assert "X5" in (final_validated.model or "")
    assert final_validated.year == 2023
    # Backend computes that budget_eur is missing
    assert "budget_eur" in final_validated.missing_fields


@pytest.mark.asyncio
async def test_step1_extraction_tunisian_arabic(gemini_adapter: GeminiAdapter) -> None:
    """Step 1: Test pure Tunisian Arabic Derja prompt."""
    message = "Salam, nheb nechri Clio 5 modil 2020 budget 35000 dinar fcr"
    req = LLMCompletionRequest(
        prompt=f"Customer message:\n<untrusted_user_message>\n{message}\n</untrusted_user_message>",
        model="gemini-3.6-flash",
    )
    validated_raw, _ = await gemini_adapter.generate_structured_output(req, VehicleRequestExtraction)
    final_validated = validate_vehicle_request(validated_raw.model_dump())

    assert final_validated.model is not None
    assert "clio" in final_validated.model.lower() or final_validated.make.lower() == "renault"
    assert final_validated.year == 2020


# ============================================================================
# STEP 2: APPROVED FAQ GROUNDING & HUMAN HANDOFF TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_step2_faq_covered_question(faq_service: FAQService) -> None:
    """Step 2: Verify question in FAQ knowledge base is answered accurately."""
    res = await faq_service.answer_question("How does vehicle import work?")
    assert len(res.answer) > 20
    # Must mention key steps like inspection/shipping/customs/Europe
    assert any(w in res.answer.lower() for w in ["europe", "shipping", "customs", "step", "râdes", "import"])


@pytest.mark.asyncio
async def test_step2_faq_missing_knowledge_triggers_human_handoff(faq_service: FAQService) -> None:
    """Step 2: Verify out-of-scope question triggers safe human agent handoff."""
    res = await faq_service.answer_question("Can I pay for my car using Bitcoin cryptocurrency?")
    # Must NOT invent Bitcoin policy, must escalate to human agent
    assert res.human_handoff_triggered is True
    assert any(kw in res.answer.lower() for kw in ["conseiller humain", "human agent", "suivi", "contact", "follow up"])


# ============================================================================
# STEP 3: AGENT BEHAVIOR POLICY CONFIGURATION TESTS
# ============================================================================

def test_step3_agent_policy_guardrails() -> None:
    """Step 3: Verify safe policy configuration constraints."""
    policy = load_agent_policy()

    assert policy.provider == "gemini"
    assert policy.mode in (AgentMode.DRAFT_THEN_SEND, AgentMode.AUTONOMOUS)
    assert policy.require_customer_confirmation is True
    assert policy.allow_price_commitments is False
    assert policy.allow_availability_commitments is False
    assert policy.allow_unconfirmed_order_creation is False
    assert policy.human_handoff_enabled is True
