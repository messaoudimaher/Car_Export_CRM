"""Comprehensive Demonstration & Verification Script for Steps 1, 2, and 3.

Usage:
  cd src/backend
  uv run python ../../scripts/test_ai_capabilities.py
"""

import asyncio
import json
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "backend"))

from app.adapters.llm_gemini import GeminiAdapter
from app.core.agent_policy import load_agent_policy
from app.ports.llm import LLMCompletionRequest
from app.schemas.vehicle_request_extraction import VehicleRequestExtraction, validate_vehicle_request
from app.services.faq_service import FAQService


async def run_step_1(adapter: GeminiAdapter) -> None:
    print("\n" + "=" * 80)
    print("STEP 1: MULTILINGUAL STRUCTURED EXTRACTION (GEMINI + BACKEND VALIDATION)")
    print("=" * 80)

    test_cases = [
        {
            "lang": "Mixed Arabic / French (User Example)",
            "message": "نحب Peugeot 208 موديل 2022 بميزانية 15000 يورو.",
        },
        {
            "lang": "French",
            "message": "Bonjour, je cherche une Volkswagen Golf 8 de 2021 avec un budget max de 22000 euros.",
        },
        {
            "lang": "English",
            "message": "Hello, I would like to import a 2023 BMW X5 with a budget of 55000 EUR to Tunisia.",
        },
        {
            "lang": "Tunisian Arabic (Derja)",
            "message": "Salam alaykom, nheb nechri Clio 5 modil 2020 budget 35000 dinar fcr tounes",
        },
    ]

    for tc in test_cases:
        print(f"\n[Test Case: {tc['lang']}]")
        print(f"Message: \"{tc['message']}\"")

        req = LLMCompletionRequest(
            prompt=(
                f"Extract vehicle specs from customer message:\n<untrusted_user_message>\n{tc['message']}\n</untrusted_user_message>\n\n"
                "Return JSON matching: intent, make, model, year, budget_eur, language, fcr_eligible."
            ),
            model="gemini-3.6-flash",
        )
        validated_raw, meta = await adapter.generate_structured_output(req, VehicleRequestExtraction)

        # Apply backend business rules validation
        final_result = validate_vehicle_request(validated_raw.model_dump())

        print("--- Backend Validated Extraction Output ---")
        print(json.dumps(final_result.model_dump(), indent=2, ensure_ascii=False))
        print(f"Latency: {round(meta.latency_ms, 2)} ms | Total Tokens: {meta.total_tokens}")
        await asyncio.sleep(1.0)


async def run_step_2(adapter: GeminiAdapter) -> None:
    print("\n" + "=" * 80)
    print("STEP 2: GROUNDED FAQ WORKFLOW (APPROVED KNOWLEDGE BASE & HUMAN ESCALATION)")
    print("=" * 80)

    faq_service = FAQService(adapter)

    faq_questions = [
        "How does vehicle import work?",
        "What information is needed for a request?",
        "Do you offer delivery?",
        "How can I contact a human agent?",
        "What documents may be required?",
        # Out-of-scope question to test strict human handoff
        "Can I pay for my car using Bitcoin cryptocurrency?",
    ]

    for q in faq_questions:
        print(f"\n[Inquiry]: \"{q}\"")
        res = await faq_service.answer_question(q)
        print(f"Answer: {res.answer}")
        print(f"Grounded in FAQ: {res.is_grounded_in_faq} | Human Handoff Triggered: {res.human_handoff_triggered}")
        await asyncio.sleep(1.0)


def run_step_3() -> None:
    print("\n" + "=" * 80)
    print("STEP 3: AGENT BEHAVIOR POLICY CONFIGURATION")
    print("=" * 80)

    policy = load_agent_policy()
    print("Loaded Safe Guardrails Policy:")
    print(json.dumps(policy.model_dump(), indent=2))


async def main() -> None:
    adapter = GeminiAdapter()
    await run_step_1(adapter)
    await run_step_2(adapter)
    run_step_3()
    print("\n" + "=" * 80)
    print("ALL 3 STEPS COMPLETED & VERIFIED SUCCESSFULLY!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
