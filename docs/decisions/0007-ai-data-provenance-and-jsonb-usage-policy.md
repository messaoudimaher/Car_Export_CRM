# ADR 0007: AI Data Provenance and JSONB Usage Policy

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM uses AI LLMs to analyze incoming WhatsApp messages, extract structured vehicle sourcing specifications (Make, Model, Year, Fuel, Budget, FCR), and generate draft responses. 

We must define how AI outputs are stored, how data provenance is tracked from raw customer message to confirmed business entities, and the architectural policy governing JSONB usage vs relationally modeled columns.

---

## 2. Decision Drivers

- **AI Non-Authoritative Guardrail (`INV-003`, `INV-006`)**: AI extractions are provisional suggestions and must never silently overwrite validated business entities.
- **Auditability & Quality Tuning**: Historical AI extractions, raw outputs, model versions, and human corrections must be preserved to evaluate model accuracy over time.
- **Relational Integrity vs Schema Flexibility**: Core domain entities must remain strictly relational for SQL querying, indexing, and type safety, while semi-structured LLM payloads require JSONB flexibility.

---

## 3. Decision Outcome

**Chosen Option**: **4-Tier Data Provenance Architecture & Strict JSONB Relational Boundary Policy**.

### 1. 4-Tier Provenance Storage Mapping:
- **Layer 1 (Source Customer Data)**: Stored immutably in `messages` table (`content`, `provider_message_id`, `created_at`).
- **Layer 2 (Provisional AI Interpretation)**: Stored in `ai_understandings` table (`intent`, `extracted_payload` JSONB, `confidence_score`, `model_name`, `prompt_version`, `status`).
- **Layer 3 (Human Review & Correction)**: Stored in `vehicle_requests` table with fields (`confirmed_by_user_id`, `confirmed_at`, `is_human_validated`, `ai_understanding_id`).
- **Layer 4 (Authoritative Business Truth)**: Enforced in relational aggregates (`leads`, `quotations`, `vehicles`).

### 2. JSONB Usage Policy:
- **Allowed for JSONB**:
  - `ai_understandings.extracted_payload`: Schema-validated JSON payload from LLM.
  - `messages.metadata`: WhatsApp provider webhook metadata (media headers, button clicks, status payloads).
  - `audit_events.payload_before` & `audit_events.payload_after`: Audit delta objects.
- **Forbidden for JSONB**:
  - Core business fields (`price_eur`, `phone_e164`, `lead_status`, `fcr_eligible`, `vin`, `valid_until`). All core domain fields MUST be explicitly typed relational columns.

---

## 4. Consequences

### Positive:
- Clear separation between AI suggestions and business ground truth.
- High query performance and type safety for all core CRM business operations.
- Full provenance tracking for model optimization and error diagnosis.

### Negative / Mitigation:
- Additional storage for storing raw AI extractions alongside confirmed vehicle request records. (Mitigated by JSONB compression and archiving policy).
