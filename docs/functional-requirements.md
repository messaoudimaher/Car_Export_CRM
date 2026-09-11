# Functional Requirements Specification

This document provides a precise, testable, ID-based functional requirements specification for **Car-Export-CRM**. All requirements map to approved product goals, business rules, user personas, and user journeys (J1–J10).

---

## 1. Business Rules Taxonomy (BR-*)

| Rule ID | Business Rule Description | Scope / Enforced In |
| :--- | :--- | :--- |
| **BR-001** | **Tenant Context Authority**: Tenant identity MUST be derived exclusively from authenticated user session tokens. Client-supplied `tenant_id` parameters are forbidden as authorization sources. | `FR-TENANT-001`, `FR-AUTH-001` |
| **BR-002** | **Multi-Tenant Row Isolation**: All database queries MUST explicitly include a `.where(Entity.tenant_id == current_tenant_id)` boundary clause. Cross-tenant reads or writes MUST return `HTTP 404 Not Found`. | `FR-TENANT-002` |
| **BR-003** | **Human Quotation Authority**: AI engine MUST NOT independently authorize or send binding export quotations. Quotation dispatch requires explicit Human Rep click/approval. | `FR-QUOTE-001`, `FR-AI-001` |
| **BR-004** | **Tunisia FCR Age Limit**: Passenger cars imported under Tunisia FCR privileges MUST be 5 years old or less at registration. The system MUST flag requests exceeding 5 years. | `FR-VREQ-002`, `FR-CUST-002` |
| **BR-005** | **European Netto/Brutto VAT Regimes**: Export quotes MUST explicitly categorize European VAT regimes (`Netto_Export` for EU business buyers / non-EU export, `Brutto_Margin` for margin scheme vehicles). | `FR-QUOTE-002` |
| **BR-006** | **Tunisia Customs Estimate Notice**: Estimated Tunisia customs duties in TND MUST be labeled as "Informational Estimate Only" on generated PDF quotes. | `FR-QUOTE-003` |
| **BR-007** | **Webhook Signature Validation**: Inbound WhatsApp webhooks MUST verify HMAC-SHA256 signatures (`X-Hub-Signature-256`) before parsing body payloads. | `FR-CONV-001` |
| **BR-008** | **Webhook Idempotency**: Inbound WhatsApp messages MUST be deduplicated using Meta message ID (`wamid`). Duplicate events MUST be safely acknowledged without duplicate storage. | `FR-CONV-002` |
| **BR-009** | **Untrusted Customer Input in AI**: Customer WhatsApp content passed to LLM calls MUST be enclosed inside `<untrusted_user_message>` tags to defend against prompt injection. | `FR-AI-002` |
| **BR-010** | **Pydantic Schema Validation for AI**: All LLM extraction outputs MUST be validated against Pydantic schemas. Unparsed freeform LLM text MUST NOT mutate system state. | `FR-AI-003` |
| **BR-011** | **Lead State Machine Validity**: Leads MUST follow valid state transitions (`New` → `Qualified` → `Sourcing` → `Quoted` → `Won`/`Lost`). Invalid state jumps are rejected. | `FR-LEAD-001` |
| **BR-012** | **Lost Lead Reopening Window**: A `Lost` lead MAY be automatically reopened to `New` if the customer sends an inbound message within 90 days of closure. | `FR-LEAD-002` |
| **BR-013** | **Pre-signed Document URLs**: Export documents (*Carte Grise*, *FCR* certs) MUST be served via short-lived pre-signed URLs with a maximum expiry of 15 minutes. | `FR-DOC-001` |
| **BR-014** | **Customer Phone Normalization**: Phone numbers MUST be normalized to E.164 format (e.g. `+21698123456`) upon ingestion to prevent duplicate profile creation. | `FR-CUST-001` |
| **BR-015** | **Manager Discount Approval**: Quotations with custom discounts exceeding 5% or margin overrides MUST require `TenantAdmin` approval before dispatch. | `FR-QUOTE-004` |
| **BR-016** | **Immutable Audit Event Logging**: Security events, role changes, data mutations, quote dispatches, and document views MUST generate immutable `AuditEvent` records. | `FR-AUDIT-001` |

---

## 2. Functional Requirements by Category

### 2.1 Authentication & Identity (FR-AUTH)

#### `FR-AUTH-001`: User Login & Token Issuance
- **Actor**: All Users (`SuperAdmin`, `TenantAdmin`, `SalesAgent`, `LogisticsAgent`).
- **Preconditions**: User account exists and `is_active == True`.
- **Behavior**: System validates credentials (email + password) and issues an encrypted JWT access token containing `user_id`, `tenant_id`, and `role`.
- **Business Rules**: `BR-001`.
- **Error Behavior**: Invalid credentials return `HTTP 401 Unauthorized` with `UNAUTHENTICATED` error code.
- **Permission**: Public endpoint.
- **Audit**: Generates `USER_LOGIN_SUCCESS` or `USER_LOGIN_FAILED`.
- **User Journey**: All journeys.
- **Priority**: **MUST**.

#### `FR-AUTH-002`: User Deactivation Enforcement
- **Actor**: System.
- **Preconditions**: User account `is_active` set to `False` by `TenantAdmin`.
- **Behavior**: System immediately rejects access tokens associated with deactivated users.
- **Error Behavior**: Returns `HTTP 401 Unauthorized`.
- **Permission**: System internal.
- **Audit**: Generates `ACCESS_DENIED_DEACTIVATED_USER`.
- **User Journey**: J9.
- **Priority**: **MUST**.

---

### 2.2 Multi-Tenancy & Tenant Boundaries (FR-TENANT)

#### `FR-TENANT-001`: Multi-Tenant Identity Context Resolution
- **Actor**: System Middleware.
- **Preconditions**: Request includes valid JWT token.
- **Behavior**: Middleware extracts `tenant_id` directly from validated JWT claims and attaches it to request execution context. Client-supplied `tenant_id` parameters in URL or body are ignored.
- **Business Rules**: `BR-001`.
- **Error Behavior**: Missing or invalid token returns `HTTP 401 Unauthorized`.
- **Permission**: System internal.
- **Audit**: Logged on authorization failure.
- **User Journey**: All journeys.
- **Priority**: **MUST**.

#### `FR-TENANT-002`: Cross-Tenant Resource Access Prevention
- **Actor**: System Repositories.
- **Preconditions**: Request authenticated.
- **Behavior**: Every database query appends `.where(Entity.tenant_id == current_tenant_id)`. If User from Tenant A requests a resource ID owned by Tenant B, system returns `HTTP 404 Not Found`.
- **Business Rules**: `BR-002`.
- **Error Behavior**: Returns `HTTP 404 Not Found` (hides resource existence).
- **Permission**: All authenticated users.
- **Audit**: Generates `SECURITY_CROSS_TENANT_ACCESS_ATTEMPT`.
- **User Journey**: All journeys.
- **Priority**: **MUST**.

---

### 2.3 Customer Management (FR-CUST)

#### `FR-CUST-001`: Customer Creation & E.164 Normalization
- **Actor**: System (Auto-ingestion) or Sales Rep (`SalesAgent`).
- **Preconditions**: Inbound WhatsApp message received or manual customer entry initiated.
- **Behavior**: System normalizes phone number to E.164 standard (e.g. `+21698123456`). If phone number exists for tenant, select existing profile; otherwise, create new `Customer` record.
- **Business Rules**: `BR-014`.
- **Error Behavior**: Invalid phone number format returns `HTTP 400 Bad Request`.
- **Permission**: `Customer:create`.
- **Audit**: Generates `CUSTOMER_CREATED`.
- **User Journey**: J1.
- **Priority**: **MUST**.

#### `FR-CUST-002`: FCR Eligibility Management
- **Actor**: Sales Rep (`SalesAgent`) or Operations Rep (`LogisticsAgent`).
- **Preconditions**: Customer record exists.
- **Behavior**: User toggles `fcr_eligible` boolean and updates customer preferred language (`fr`, `ar_tn`, `en`).
- **Business Rules**: `BR-004`.
- **Permission**: `Customer:update`.
- **Audit**: Generates `CUSTOMER_UPDATED`.
- **User Journey**: J4, J7.
- **Priority**: **MUST**.

---

### 2.4 WhatsApp Conversations & Messages (FR-CONV / FR-MSG)

#### `FR-CONV-001`: Webhook HMAC Verification & Processing
- **Actor**: System (Webhook Endpoint).
- **Preconditions**: Inbound HTTP POST to `/api/v1/webhooks/whatsapp`.
- **Behavior**: System calculates HMAC-SHA256 signature over request body using `WHATSAPP_APP_SECRET` and compares with `X-Hub-Signature-256` header. If valid, return `HTTP 200 OK` and enqueue background worker job.
- **Business Rules**: `BR-007`.
- **Error Behavior**: Invalid signature returns `HTTP 401 Unauthorized`; drop payload.
- **Permission**: Public webhook endpoint with signature verification.
- **Audit**: Generates `WEBHOOK_SIGNATURE_FAILED` on failure.
- **User Journey**: J1.
- **Priority**: **MUST**.

#### `FR-CONV-002`: Message Deduplication via `wamid`
- **Actor**: System (Background Worker).
- **Preconditions**: Inbound webhook job dequeued.
- **Behavior**: System checks if `provider_message_id` (`wamid`) already exists in tenant context. If duplicate, log warning and exit job safely without saving duplicate message.
- **Business Rules**: `BR-008`.
- **Permission**: System internal.
- **Audit**: Generates `DUPLICATE_MESSAGE_IGNORED`.
- **User Journey**: J1.
- **Priority**: **MUST**.

#### `FR-MSG-001`: Outbound WhatsApp Message Dispatch
- **Actor**: Sales Rep (`SalesAgent`).
- **Preconditions**: Active conversation thread; Rep assigned or thread unassigned.
- **Behavior**: Rep inputs text response or approves AI draft. System calls `WhatsAppProvider.send_text_message()`, creates outbound `Message` record, and updates thread `last_message_at`.
- **Error Behavior**: If BSP API returns error, mark message as `Failed` in UI and allow manual retry.
- **Permission**: `Conversation:respond`.
- **Audit**: Generates `MESSAGE_DISPATCHED`.
- **User Journey**: J2.
- **Priority**: **MUST**.

---

### 2.5 WhatsApp Operational Inbox Workspace (FR-INBOX)

#### `FR-INBOX-001`: Operational 3-Panel Workspace Display
- **Actor**: Sales Rep (`SalesAgent`), Manager (`TenantAdmin`).
- **Preconditions**: User authenticated.
- **Behavior**: Displays 3-panel UI layout: (Panel 1: Conversation List with search/filter badges | Panel 2: Active Chat History | Panel 3: Customer & AI Vehicle Request Sidebar).
- **Permission**: `Conversation:view`.
- **User Journey**: J2.
- **Priority**: **MUST**.

#### `FR-INBOX-002`: Conversation Assignment & Queue Filters
- **Actor**: Sales Rep (`SalesAgent`), Manager (`TenantAdmin`).
- **Preconditions**: Conversation thread status `PendingAgent`.
- **Behavior**: Rep can filter by `Unassigned`, `Assigned to Me`, or `All`. Rep clicks "Claim Thread" to assign `assigned_agent_id` to themselves.
- **Permission**: `Conversation:assign`.
- **Audit**: Generates `CONVERSATION_ASSIGNED`.
- **User Journey**: J2, J8.
- **Priority**: **MUST**.

---

### 2.6 AI Understanding & Extraction (FR-AI)

#### `FR-AI-001`: Schema-Validated Vehicle Request Extraction
- **Actor**: AI Engine (Background Worker).
- **Preconditions**: Inbound text message saved.
- **Behavior**: Worker passes message text enclosed in `<untrusted_user_message>` tags to LLM. Parses response into Pydantic schema `VehicleRequestExtraction` (Make, Model, Year, Fuel, Budget, FCR). Creates `AIUnderstanding` record.
- **Business Rules**: `BR-003`, `BR-009`, `BR-010`.
- **Error Behavior**: Malformed JSON triggers fallback parser. Low confidence (< 0.6) marks extraction as `Provisional Review Required`.
- **Permission**: System internal.
- **Audit**: Generates `AI_EXTRACTION_COMPLETED`.
- **User Journey**: J3.
- **Priority**: **MUST**.

#### `FR-AI-002`: Human Validation & Correction of AI Output
- **Actor**: Sales Rep (`SalesAgent`).
- **Preconditions**: Provisional AI extraction card displayed in Inbox sidebar.
- **Behavior**: Rep reviews extracted parameters, corrects any field, and clicks "Confirm Request". System updates `VehicleRequest` record to `Validated`.
- **Business Rules**: `BR-003`.
- **Permission**: `Lead:update`.
- **Audit**: Generates `AI_EXTRACTION_CORRECTED_BY_HUMAN`.
- **User Journey**: J4.
- **Priority**: **MUST**.

---

### 2.7 Vehicle Requests (FR-VREQ)

#### `FR-VREQ-001`: Vehicle Request Specification Management
- **Actor**: Sales Rep (`SalesAgent`).
- **Preconditions**: Customer record exists.
- **Behavior**: Rep views or manually creates structured `VehicleRequest` specifying Make, Model, Min Year, Fuel Type, Budget (EUR), FCR required status, and destination port (Rades / La Goulette).
- **Business Rules**: `BR-004`.
- **Permission**: `Lead:create`, `Lead:update`.
- **User Journey**: J4, J5.
- **Priority**: **MUST**.

---

### 2.8 Lead Pipeline Management (FR-LEAD)

#### `FR-LEAD-001`: Lead State Machine Progression
- **Actor**: Sales Rep (`SalesAgent`), Manager (`TenantAdmin`).
- **Preconditions**: Lead record exists.
- **Behavior**: Rep transitions lead through valid state pipeline: `New` → `Qualified` → `Sourcing` → `Quoted` → `Won` / `Lost`.
- **Business Rules**: `BR-011`.
- **Error Behavior**: Invalid state jump (e.g. `New` directly to `Won`) returns `HTTP 422 Unprocessable Entity`.
- **Permission**: `Lead:update`.
- **Audit**: Generates `LEAD_STATE_TRANSITION`.
- **User Journey**: J5.
- **Priority**: **MUST**.

#### `FR-LEAD-002`: Lost Lead Reason Tracking & Reopening
- **Actor**: Sales Rep (`SalesAgent`) or System (Auto-reopen).
- **Preconditions**: Lead set to `Lost`.
- **Behavior**: Rep selects lost reason (`Out of Budget`, `Bought Locally`, `Unresponsive`). If customer sends new message within 90 days, system reopens lead to `New`.
- **Business Rules**: `BR-012`.
- **Permission**: `Lead:update`.
- **Audit**: Generates `LEAD_REOPENED`.
- **User Journey**: J5.
- **Priority**: **MUST**.

---

### 2.9 Follow-up Scheduling (FR-FOLLOWUP)

#### `FR-FOLLOWUP-001`: Scheduled Follow-up Reminders
- **Actor**: Sales Rep (`SalesAgent`).
- **Preconditions**: Lead or Conversation active.
- **Behavior**: Rep creates `FollowUp` task setting `due_at` timestamp and notes. When `due_at` timestamp is reached, system displays alert badge in rep inbox.
- **Permission**: `Lead:update`.
- **Audit**: Generates `FOLLOWUP_SCHEDULED`.
- **User Journey**: J6.
- **Priority**: **MUST**.

---

### 2.10 Export Quotations (FR-QUOTE)

#### `FR-QUOTE-001`: Export Quotation Calculation & PDF Dispatch
- **Actor**: Sales Rep (`SalesAgent`).
- **Preconditions**: Lead in `Sourcing` state; sourced vehicle selected.
- **Behavior**: Rep enters vehicle price, EU VAT regime (`Netto_Export`, `Brutto_Margin`), shipping fee, and transit insurance. System computes total price in EUR and estimated Tunisia customs in TND (labeled informational). Generates PDF and dispatches via WhatsApp.
- **Business Rules**: `BR-003`, `BR-005`, `BR-006`.
- **Permission**: `Quotation:create`.
- **Audit**: Generates `QUOTE_GENERATED`, `QUOTE_DISPATCHED`.
- **User Journey**: J7.
- **Priority**: **MUST**.

#### `FR-QUOTE-002`: Manager Approval for Discount Overrides
- **Actor**: Manager (`TenantAdmin`).
- **Preconditions**: Quote created with custom discount > 5% or custom margin override.
- **Behavior**: Quote marked as `Draft (Pending Approval)`. Manager reviews quote details and clicks "Approve Quote". Rep can then dispatch quote to customer.
- **Business Rules**: `BR-015`.
- **Permission**: `Quotation:approve`.
- **Audit**: Generates `QUOTE_APPROVED`.
- **User Journey**: J7, J8.
- **Priority**: **MUST**.

---

### 2.11 Document Management (FR-DOC)

#### `FR-DOC-001`: Secure Document Upload & Pre-signed URL Viewing
- **Actor**: Sales Rep (`SalesAgent`), Operations Rep (`LogisticsAgent`).
- **Preconditions**: Customer or Lead record exists.
- **Behavior**: User uploads export file (*Carte Grise*, *FCR* cert). System stores file in private object storage. When requested, system generates short-lived pre-signed URL (15-min expiry).
- **Business Rules**: `BR-013`.
- **Error Behavior**: Cross-tenant document request returns `HTTP 404 Not Found`.
- **Permission**: `Document:view`, `Document:upload`.
- **Audit**: Generates `DOCUMENT_UPLOADED`, `DOCUMENT_VIEWED`.
- **User Journey**: J10.
- **Priority**: **MUST**.

---

### 2.12 Audit & Security Logging (FR-AUDIT)

#### `FR-AUDIT-001`: Immutable Audit Event Creation
- **Actor**: System.
- **Preconditions**: Security event or state-mutating business action performed.
- **Behavior**: System creates immutable `AuditEvent` record containing `tenant_id`, `user_id`, `action`, `resource_type`, `resource_id`, `changes`, and `timestamp`.
- **Business Rules**: `BR-016`.
- **Permission**: `Audit:view` (for managers/admins).
- **User Journey**: All journeys.
- **Priority**: **MUST**.

---

## 3. Given / When / Then Acceptance Criteria

### Acceptance Criteria AC-01: Multi-Tenant Query Isolation (`FR-TENANT-002`)
- **Given**: A Sales Rep is authenticated under Tenant A context.
- **And**: A Customer record `cust_123` exists belonging to Tenant B.
- **When**: The Sales Rep sends request `GET /api/v1/customers/cust_123`.
- **Then**: The system denies access and returns `HTTP 404 Not Found`.
- **And**: No data belonging to Tenant B is exposed.
- **And**: An audit event `SECURITY_CROSS_TENANT_ACCESS_ATTEMPT` is recorded.

### Acceptance Criteria AC-02: Non-Authoritative AI Output Guardrail (`FR-AI-001`, `BR-003`)
- **Given**: An inbound customer message *"Je veux acheter la Golf 8 à 15000€"*.
- **When**: The AI Engine processes the message.
- **Then**: The system extracts a provisional `VehicleRequest` card with budget €15,000.
- **And**: The system DOES NOT issue a quote or send an outbound WhatsApp response automatically.
- **And**: The provisional card is displayed in the rep Inbox sidebar tagged `AI Extracted (Unconfirmed)`.

### Acceptance Criteria AC-03: Quotation Dispatch Approval (`FR-QUOTE-001`, `BR-003`)
- **Given**: A Sales Rep prepares an export quote for Lead `lead_456`.
- **When**: The Sales Rep clicks "Generate PDF & Send Quote".
- **Then**: The system validates pricing inputs, generates styled PDF quote `QT-2026-0042`, and sets status to `Sent`.
- **And**: The PDF quote is dispatched to the customer's WhatsApp thread.
- **And**: An audit event `QUOTE_DISPATCHED` is recorded.

---

## 4. User Journey Traceability Matrix

| Requirement ID | Related User Journeys | Priority |
| :--- | :--- | :---: |
| `FR-AUTH-001` | All Journeys (J1–J10) | **MUST** |
| `FR-TENANT-001`, `FR-TENANT-002` | All Journeys (J1–J10) | **MUST** |
| `FR-CUST-001`, `FR-CUST-002` | J1, J4, J7, J10 | **MUST** |
| `FR-CONV-001`, `FR-CONV-002` | J1 | **MUST** |
| `FR-MSG-001` | J2 | **MUST** |
| `FR-INBOX-001`, `FR-INBOX-002` | J2, J8 | **MUST** |
| `FR-AI-001`, `FR-AI-002` | J3, J4 | **MUST** |
| `FR-VREQ-001` | J4, J5 | **MUST** |
| `FR-LEAD-001`, `FR-LEAD-002` | J5 | **MUST** |
| `FR-FOLLOWUP-001` | J6 | **MUST** |
| `FR-QUOTE-001`, `FR-QUOTE-002` | J7, J8 | **MUST** |
| `FR-DOC-001` | J10 | **MUST** |
| `FR-AUDIT-001` | All Journeys (J1–J10) | **MUST** |

---

## 5. Non-Functional Requirements (High Level)

1. **Security & Data Isolation**: 100% of API endpoints MUST enforce tenant isolation derived from authenticated JWT claims. Zero cross-tenant data leaks permitted.
2. **Performance**: Inbound WhatsApp webhook handlers MUST process HMAC validation, deduplication, and enqueue background jobs within < 200 ms.
3. **Availability**: Target 99.5% uptime for API controllers and WhatsApp message ingestion queues.
4. **Data Encryption**: TLS 1.3 enforced in transit; AES-256 disk encryption at rest for database and S3 storage.
5. **Observability**: All application logs MUST format as structured JSON containing `correlation_id`, `tenant_id`, and `user_id`.

---

## 6. Open Questions & Decisions

### Blocking Questions:
- **None**. All core functional requirements for the MVP scope are fully established.

### Non-Blocking Questions (Can Be Decided Later):
- Should default sales rep follow-up reminder notification interval default to 24 hours or 48 hours? (Default: 48 hours, tenant configurable).
- Should generated PDF export quotes expire automatically after 7 or 14 days? (Default: 14 days).
