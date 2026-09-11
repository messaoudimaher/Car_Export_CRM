# ADR 0012: Five-Layer AI Output Validation and HITL Boundary

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM uses AI LLMs to analyze incoming WhatsApp messages, extract structured vehicle sourcing requests, and draft suggested replies for sales reps.

Allowing AI LLM outputs to directly mutate authoritative system state (prices, inventory availability, discounts, binding export quotes, legal export document validations) introduces severe risks of prompt injection attacks, hallucinated prices, and legal liability.

---

## 2. Decision Drivers

- **AI Non-Authoritative Invariant (`INV-003`, `INV-006`)**: AI is an assistant, never an autonomous business authority.
- **Prompt Injection Defense**: Untrusted customer messages must be safely passed to LLMs without allowing customer text to override system role boundaries.
- **Data Provenance**: Clear separation between provisional AI extractions (`Layer 2`), rep validations (`Layer 3`), and authoritative business state (`Layer 4`).

---

## 3. Decision Outcome

**Chosen Option**: **Five-Layer Validation Pipeline & Mandatory Human-in-the-Loop (HITL) Confirmation Boundary**.

### Specifications:

#### 1. Five-Layer Validation Pipeline:
1. **Layer 1 (Provider Response Validation)**: Verify HTTP 200 OK from LLM provider API and validate non-empty string payload.
2. **Layer 2 (JSON Schema Validation)**: Validate structured output against strict JSON Schema definitions (`VehicleRequestExtraction`, `AIUnderstanding`). Unparsed freeform text is rejected immediately (`BR-010`). *(Implementation Note: Python/FastAPI layer may use Pydantic v2 for runtime schema validation).*
3. **Layer 3 (Business Domain Rule Validation)**: Enforce domain invariants (e.g. check Tunisia FCR 5-year vehicle age limit `INV-004`; check positive budget amounts).
4. **Layer 4 (RBAC Authorization)**: Verify that the authenticated user confirming the AI output holds necessary RBAC permissions (`Lead:update`) under tenant context derived strictly from authenticated session/JWT tokens (`BR-001`). Model, customer text, or prompt payloads can NEVER specify or override tenant scope.
5. **Layer 5 (Human-in-the-Loop Confirmation & Persistence)**: Require explicit sales rep click/approval in the B2B Inbox UI (`POST /api/v1/leads/{id}/vehicle-request/confirm`). Only upon human click does the provisional suggestion become authoritative business truth (`VehicleRequest`).

#### 2. Defense-in-Depth Prompt Injection Security:
- XML tags (e.g. `<untrusted_user_message> ... </untrusted_user_message>`) are used as a prompt-structuring technique (`BR-009`) to visually segment raw customer input for the LLM.
- **Critical Security Boundary**: XML tags alone are NOT a security boundary. Prompt injection defense relies on **Defense-in-Depth**:
  - Explicit trust boundaries (Customer text is always untrusted input).
  - System instruction & data separation.
  - Strict JSON Schema output validation (Layer 2).
  - Business domain validation rules (Layer 3).
  - Server-side RBAC & Tenant Authorization (Layer 4).
  - Restricted tool access (AI cannot execute direct database mutations or API actions).
  - Mandatory Human Confirmation (Layer 5).

---

## 4. Consequences

### Positive:
- Zero risk of AI hallucinating binding export prices, discounts, or sending unvetted customer messages.
- Total defense-in-depth protection against indirect prompt injection attacks embedded in WhatsApp messages or retrieved documents.
- Full traceability and audit logging (`AI_EXTRACTION_CORRECTED_BY_HUMAN`).

### Negative / Mitigation:
- Requires sales rep interaction in the Inbox UI rather than fully autonomous unvetted chatbots. (Aligned 100% with product vision and business rule `BR-003`).

