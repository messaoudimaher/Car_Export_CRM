# ADR 0018: Provider-Agnostic External Integration Ports, Local-First Architecture, and Multi-Tenant WhatsApp Integration

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM requires integrations with WhatsApp messaging (Meta Cloud API), Large Language Models (LLMs), Embeddings, and Object Storage.

To support rapid developer onboarding, reproducible automated testing, zero cloud lock-in, and multi-tenant SaaS scaling, the application architecture must satisfy five key requirements:
1. **Local-First MVP Development**: The full stack must be runnable locally without requiring paid cloud infrastructure or commercial vendor accounts.
2. **Provider Abstraction**: Domain and application modules must depend on generic interface ports rather than concrete vendor SDKs.
3. **Multi-Tenant WhatsApp Accounts**: The platform must support multi-tenant business numbers (connecting multiple customer WhatsApp numbers) without modifying domain code.
4. **WhatsApp Customer Onboarding**: Support Meta-supported Embedded Signup workflows for onboarding customer WhatsApp Business accounts.
5. **AI Guardrails & Non-Authoritative Boundaries**: AI chatbots must qualify incoming conversations while strictly remaining non-authoritative over business data (prices, inventory, delivery dates, contracts, tax calculations).

---

## 2. Decision Drivers

- **Developer Ergonomics**: Developers can spin up and test the full application locally using lightweight local service containers.
- **Vendor Independence**: Ability to swap infrastructure providers (e.g. MinIO to S3, Ollama to OpenAI/Gemini, DemoWhatsApp to Meta Cloud API) purely via configuration settings.
- **Tenant Isolation & Security**: Webhook handlers must resolve tenant context from verified database bindings (`phone_number_id` -> `WhatsAppAccount` -> `Tenant`) and never trust client-supplied tenant identifiers.
- **Ground Truth Integrity**: Prevent AI hallucination risks by maintaining PostgreSQL as the sole system of record for pricing, inventory, delivery, and tax rules.

---

## 3. Architecture & Specifications

### 3.1 Local-First Reference Implementation vs Production Topology

| Capability / Port | Interface Port (`app/ports/`) | Local MVP Reference Adapter (`app/adapters/`) | Production Cloud Adapter (`app/adapters/`) |
| :--- | :--- | :--- | :--- |
| **Messaging** | `WhatsAppProvider` | `DemoWhatsAppProvider` | `MetaWhatsAppProvider` (Meta Cloud API) |
| **Object Storage** | `ObjectStorageProvider` | `MinIOStorageAdapter` | `S3StorageAdapter` (AWS S3 or S3-compatible) |
| **LLM Orchestration** | `LLMProvider` | `OllamaLLMAdapter` | `OpenAILLMAdapter` / `GeminiLLMAdapter` |
| **Database** | Database Engine | Local PostgreSQL + `pgvector` | Managed PostgreSQL + `pgvector` |
| **Task Queue / Cache** | Task Queue Engine | Local Redis | Managed Redis |

*Rule*: Paid cloud services (AWS S3, OpenAI, Gemini, paid Redis) are optional production adapters and MUST NOT be mandatory for local MVP development.

---

### 3.2 Multi-Tenant WhatsApp Data Model & Webhook Ingestion

The domain relationship for multi-tenant WhatsApp accounts is structured as:

```text
Tenant (1)
  └── WhatsAppAccount (N)
        ├── id (UUIDv7)
        ├── tenant_id (UUIDv7 FK)
        ├── phone_number_id (String, Indexed)
        ├── display_phone_number (String)
        ├── waba_id (String - WhatsApp Business Account ID)
        ├── access_token_vault_ref (String - Encrypted credential reference)
        ├── status (Enum: ACTIVE, DISCONNECTED, PENDING_VERIFICATION)
        └── created_at / updated_at
```

#### Inbound Webhook Resolution Pipeline:
```text
Inbound Meta Webhook (POST /api/v1/webhooks/whatsapp)
        ↓
Extract Meta `entry[].changes[].value.metadata.phone_number_id`
        ↓
Query Database: Lookup `WhatsAppAccount` WHERE `phone_number_id` == extracted `phone_number_id`
        ↓
Resolve `Tenant` context (`WhatsAppAccount.tenant_id`)
        ↓
Resolve or Create `Customer` (by sender E.164 phone number) & `Conversation` thread
        ↓
Persist Inbound Message Record in PostgreSQL under resolved `tenant_id`
        ↓
Enqueue Background Worker Job for AI Qualification & Intent Processing
```

*Security Invariant*: Webhook handlers resolve `tenant_id` strictly from the verified `WhatsAppAccount.phone_number_id` lookup in PostgreSQL. Client-supplied `tenant_id` headers or parameters are NEVER trusted.

---

### 3.3 WhatsApp Customer Onboarding Concept (Embedded Signup)

Future customer onboarding follows Meta's standard Embedded Signup workflow:
1. Sales Rep / Tenant Admin clicks "Connect WhatsApp" in CRM settings.
2. CRM initiates Meta Embedded Signup OAuth pop-up dialog.
3. Customer authorizes their WhatsApp Business Account (WABA) and phone number assets.
4. Meta returns access tokens and asset IDs (`phone_number_id`, `waba_id`).
5. CRM securely stores the new `WhatsAppAccount` record bound to the user's `tenant_id`.
6. Zero application or domain code changes are required when onboarding new customer business numbers.

---

### 3.4 AI Qualification & Non-Authoritative Guardrails

```text
Inbound WhatsApp Message
        ↓
Conversation Thread Context
        ↓
AI Qualification & Intent Extraction (`LLMProvider`)
        ↓
Intent Classification & Schema Extraction
        ├── Simple FAQ / Info Query ──> Automated Suggested Response (Provisional)
        └── Vehicle Buying Request ──> Generate Lead / VehicleRequest Proposal
        ↓
Human Escalation & Approval Gate (Sales Rep Inbox)
        ├── Sales Rep Confirms / Edits Draft
        └── System Executes Authoritative State Mutation (Database / Outbound Message)
```

#### AI Ground Truth Boundaries:
- AI outputs are classified strictly as **proposals/suggestions**.
- The AI assistant **MUST NOT** autonomously invent or commit:
  - Vehicle prices or discounts
  - Inventory availability status
  - Delivery / shipping dates
  - Legally binding FCR export documents or customs tax calculations
- Business ground truth resides exclusively in authoritative PostgreSQL entity records managed by human sales representatives.

---

## 4. Decision Outcome

**Status**: Approved.
All completed workstreams (WS-01, WS-02, WS-03) and future workstreams (WS-04 through WS-11) must adhere strictly to these provider abstractions, local-first capabilities, multi-tenant WhatsApp mappings, and AI safety guardrails.
