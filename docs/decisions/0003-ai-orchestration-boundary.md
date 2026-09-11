# ADR 0003: AI Non-Authoritative Orchestration Boundary

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM uses AI LLM models to detect intent, extract vehicle sourcing parameters from customer WhatsApp messages, and generate response drafts for sales reps.

Allowing AI models to directly mutate authoritative system state (prices, inventory reservations, delivery commitments, legal quote dispatches) introduces severe risks of hallucinated pricing, prompt injection vulnerabilities, and legal liability.

---

## 2. Decision Drivers

- **Business Accountability**: Binding export quotes and financial commitments require human employee authorization.
- **Security & Safety**: Customer WhatsApp inputs are untrusted and vulnerable to instruction-override attacks.
- **Pydantic Validation**: All structured outputs must pass strict schema validation before application processing.

---

## 3. Decision Outcome

**Chosen Option**: **Controlled Non-Authoritative AI Orchestration**.

### Specifications:
1. **Data Provenance**: AI output is explicitly classified as Layer 2 (`Provisional AI Interpretation`).
2. **Schema Enforcement**: All LLM outputs MUST be parsed into Pydantic models (`VehicleRequestExtraction`, `AIUnderstanding`). Freeform text mutations are forbidden.
3. **Prompt Safety**: User inputs are wrapped in `<untrusted_user_message>` tags with system role boundary rules.
4. **Mandatory Human Approval**: Quotation dispatches and financial commitments REQUIRE explicit Sales Rep or Manager click/approval.

### Consequences:
- **Positive**: 0% risk of AI hallucinating binding export prices or sending unvetted customer messages.
- **Negative**: Sales reps must click "Confirm" or "Send" in the Inbox UI rather than having fully autonomous chatbots.
