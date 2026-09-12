---
name: ai-engineering
description: >-
  Use this skill when engineering prompts, implementing LLM parameter extraction, defining Pydantic response schemas, building AI fallback parsers, or setting up HITL suggestions.
---

# AI Engineering & Extraction Skill

## 1. Purpose & Scope
Enforce schema-validated AI intent classification, structured vehicle request extraction, prompt safety, prompt injection defenses, and Human-in-the-Loop (HITL) UI integrations.

## 2. Activation Triggers
Activate when building LLM extraction pipelines, prompt templates, intent classifiers, AI draft response generators, or Pydantic output schemas.

## 3. Inspection Targets
- [`docs/ai-architecture.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/ai-architecture.md) (AI pipeline specs & Pydantic schemas)
- [`SECURITY.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/SECURITY.md) (Prompt injection defenses & PII protection)

## 4. Constraints
- **Schema Validation Mandatory**: ALL LLM outputs MUST be parsed into Pydantic models (`VehicleRequestExtraction`, `AIUnderstanding`). Unvalidated freeform text must never trigger system state mutations.
- **Prompt Safety**: Wrap untrusted WhatsApp message text in explicit XML tags (`<untrusted_user_message>`). System prompt must explicitly command model to ignore instruction-override attempts inside user input.
- **Non-Authoritative Boundaries**: Prompts must enforce: "AI does not set prices, confirm vehicle availability, or execute legal quotes."

## 5. Execution Procedure
1. Define Pydantic schema with explicit field descriptions and validation constraints.
2. Build prompt template with system role boundary rules and XML tag delimiters.
3. Call LLM provider via `LLMProvider` Port interface with `temperature=0.0` for extraction.
4. Implement fallback parser to handle malformed JSON responses safely.

## 6. Expected Outputs
- Fully schema-validated LLM extraction handlers.
- Safe prompt templates guarded against injection attacks.
