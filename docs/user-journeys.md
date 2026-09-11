# User Journeys & Operational Workflows

This document defines the core user personas, conceptual RBAC permissions, tenant security invariants, detailed end-to-end user journeys (J1–J10), workflow lifecycles, and operational UX principles for **Car-Export-CRM**.

---

## 1. User Roles & Conceptual RBAC Permission Matrix

### 1.1 Role Definitions
- **`SuperAdmin`**: System administrator responsible for tenant provisioning and platform-wide monitoring.
- **`TenantAdmin`**: Business owner / tenant administrator responsible for team management, channel configuration, and high-level pipeline auditing.
- **`SalesAgent`**: Sales representative responsible for customer conversations, lead qualification, quote generation, and follow-up tracking.
- **`LogisticsAgent`**: Sourcing and operations representative responsible for vehicle sourcing, cost calculations, export documentation (*Carte Grise*, *FCR*), and shipping tracking.

### 1.2 Permission Matrix

| Resource | Action | SuperAdmin | TenantAdmin | SalesAgent | LogisticsAgent |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Customer** | `view`, `create`, `update` | Yes | Yes | Yes | Yes |
| **Customer** | `delete` | Yes | Yes | No | No |
| **Conversation** | `view`, `assign`, `respond`, `resolve` | Yes | Yes | Yes (Assigned/Unassigned) | View Only |
| **Lead** | `view`, `create`, `update`, `assign` | Yes | Yes | Yes (Assigned) | View Only |
| **Vehicle** | `view`, `create`, `update` | Yes | Yes | View Only | Yes |
| **Quotation** | `view`, `create` | Yes | Yes | Yes | Yes |
| **Quotation** | `approve` (High Discount / Margin Override) | Yes | Yes | No | No |
| **Document** | `view`, `upload` | Yes | Yes | Yes | Yes |
| **Document** | `delete` | Yes | Yes | No | No |
| **User Management** | `view`, `invite`, `deactivate`, `change_role` | Yes | Yes | No | No |
| **Audit Logs** | `view` | Yes | Yes | No | No |

---

## 2. Fundamental Security Invariant: Tenant Isolation

> **SECURITY INVARIANT**: Every user belongs to an authorized Tenant. All resource accesses MUST derive tenant identity strictly from authenticated JWT / session claims. 

### Rules:
1. **Never Trust Client Payloads**: Client-supplied `tenant_id` parameters in URL paths, query parameters, request headers, or JSON bodies MUST NEVER be trusted as an authorization source.
2. **Repository Boundary Enforcement**: All database queries MUST explicitly include a `.where(Entity.tenant_id == current_tenant_id)` clause.
3. **IDOR Defense**: Accessing resource `GET /api/v1/leads/{lead_id}` belonging to Tenant A by a user from Tenant B MUST return `404 Not Found`.

---

## 3. End-to-End User Journeys (J1 through J10)

### Journey J1: Inbound WhatsApp Inquiry Ingestion & System Thread Creation
- **START**: Customer sends a WhatsApp text message to the tenant's business WhatsApp phone number.
- **ACTOR**: System (Automated Ingestion Pipeline).
- **TRIGGER**: WhatsApp Cloud API webhook callback received.
- **PRECONDITIONS**: Webhook signature (`X-Hub-Signature-256`) is valid; tenant WhatsApp channel is active.
- **MAIN FLOW**:
  1. System verifies HMAC signature and deduplicates provider `wamid`.
  2. System extracts sender phone number (`E.164`).
  3. System queries Customer directory for matching `phone_number` under tenant context.
  4. *Branch*: If customer exists, select customer record; if customer does not exist, create new `Customer` profile.
  5. System selects existing active `WhatsAppConversation` or creates a new conversation thread with status `PendingAgent`.
  6. Message payload saved to `Message` entity.
  7. Async background job triggered for AI intent and entity extraction.
- **ALTERNATIVE FLOWS**:
  - Inbound media (image/document): System stores file securely and creates `Message` record with `media_url`.
- **ERROR CASES**:
  - Webhook signature invalid → Reject with HTTP 401; drop payload; log security audit event.
  - Webhook payload malformed → Log error, respond HTTP 200 to prevent BSP webhook retries.
- **END STATE**: Conversation thread updated in inbox unassigned queue; AI extraction job enqueued.
- **AUDIT EVENTS**: `WHATSAPP_MESSAGE_INGESTED`, `CUSTOMER_AUTO_CREATED` (if new).
- **PERMISSION REQUIREMENTS**: None (Public webhook endpoint with signature verification).

---

### Journey J2: Sales Rep Manages Active Conversation Thread in Operational Inbox
- **START**: Sales Rep opens the WhatsApp Inbox workspace in the web app.
- **ACTOR**: Sales Rep (`SalesAgent`).
- **TRIGGER**: Rep clicks on an unassigned or assigned conversation thread in the Inbox sidebar.
- **PRECONDITIONS**: Rep is authenticated; conversation belongs to rep's tenant.
- **MAIN FLOW**:
  1. Rep views conversation message history, customer details, and extracted vehicle request card.
  2. Rep assigns unassigned conversation to themselves.
  3. Rep types a custom response or selects an AI-suggested response draft.
  4. Rep clicks "Send".
  5. System sends message via `WhatsAppProvider` adapter and updates conversation `last_message_at`.
- **ALTERNATIVE FLOWS**:
  - Rep marks conversation as `Resolved` or `Archived`.
- **ERROR CASES**:
  - WhatsApp BSP dispatch fails → Display error alert badge on message; allow rep retry.
- **END STATE**: Message dispatched to customer WhatsApp; conversation thread updated.
- **AUDIT EVENTS**: `CONVERSATION_ASSIGNED`, `MESSAGE_DISPATCHED`.
- **PERMISSION REQUIREMENTS**: `Conversation:view`, `Conversation:assign`, `Conversation:respond`.

---

### Journey J3: AI Engine Extracts Intent & Vehicle Parameters
- **START**: Inbound message saved to database.
- **ACTOR**: AI Subsystem (Background Worker).
- **TRIGGER**: Ingestion pipeline enqueues extraction task.
- **PRECONDITIONS**: Message text available; LLM adapter active.
- **MAIN FLOW**:
  1. Background worker loads message content and customer context.
  2. Worker passes text wrapped in `<untrusted_user_message>` tags to LLM via `LLMProvider` adapter.
  3. LLM executes classification and parameter extraction (`temperature=0.0`).
  4. Output parsed into Pydantic schema `VehicleRequestExtraction`.
  5. System creates `AIUnderstanding` record attached to message.
  6. If intent is `SourcingInquiry` and no active vehicle request exists, create provisional `VehicleRequest` record.
- **ALTERNATIVE FLOWS**:
  - Customer message is general FAQ or greetings → Extract intent `GeneralQuestion`, generate draft reply, skip vehicle request creation.
- **ERROR CASES**:
  - LLM output fails schema validation → Trigger fallback regex parser; log warning.
- **END STATE**: Provisional `AIUnderstanding` and `VehicleRequest` attached to customer lead card.
- **AUDIT EVENTS**: `AI_EXTRACTION_COMPLETED`.
- **PERMISSION REQUIREMENTS**: System internal execution.

---

### Journey J4: Sales Rep Reviews & Validates AI Extraction Card
- **START**: Rep views customer thread in Inbox workspace.
- **ACTOR**: Sales Rep (`SalesAgent`).
- **TRIGGER**: Rep inspects the "AI Extracted Vehicle Request" sidebar card.
- **PRECONDITIONS**: Conversation has attached `VehicleRequest` generated by AI.
- **MAIN FLOW**:
  1. Rep reviews extracted make, model, year range, budget, fuel type, and FCR status.
  2. Rep corrects any mis-extracted field (e.g. adjusts budget from €15,000 to €18,000).
  3. Rep clicks "Validate & Confirm Request".
  4. System updates `VehicleRequest` status to `Validated` and updates associated Lead state to `Qualified`.
- **END STATE**: Vehicle request validated by human rep; Lead progresses to `Qualified`.
- **AUDIT EVENTS**: `VEHICLE_REQUEST_VALIDATED`, `LEAD_STATUS_UPDATED`.
- **PERMISSION REQUIREMENTS**: `Lead:update`, `Customer:update`.

---

### Journey J5: Sales Rep Creates or Updates a Lead
- **START**: Customer inquiry confirmed as a genuine export buying opportunity.
- **ACTOR**: Sales Rep (`SalesAgent`).
- **TRIGGER**: Rep clicks "Convert to Qualified Lead" or updates Lead pipeline card.
- **PRECONDITIONS**: Customer profile exists.
- **MAIN FLOW**:
  1. Rep selects priority (`Low`, `Medium`, `High`, `Urgent`).
  2. Rep attaches target `VehicleRequest`.
  3. Rep selects pipeline stage (`Qualified`, `Sourcing`, `Quoted`).
  4. System updates Lead record and logs state transition timestamp.
- **ALTERNATIVE FLOWS**:
  - Customer declines or cancels → Rep updates state to `Lost` with lost reason (`Out of Budget`, `Bought Locally`, `Unresponsive`).
- **END STATE**: Lead state machine updated in CRM pipeline board.
- **AUDIT EVENTS**: `LEAD_CREATED`, `LEAD_STAGE_CHANGED`.
- **PERMISSION REQUIREMENTS**: `Lead:create`, `Lead:update`.

---

### Journey J6: Sales Rep Schedules a Follow-up
- **START**: Rep finishes communicating with customer and needs to schedule a future check-in.
- **ACTOR**: Sales Rep (`SalesAgent`).
- **TRIGGER**: Rep clicks "Schedule Follow-up" in conversation sidebar.
- **PRECONDITIONS**: Lead or conversation thread active.
- **MAIN FLOW**:
  1. Rep selects due date/time (e.g. 48 hours later).
  2. Rep enters reminder notes (e.g. *"Check if customer received FCR certificate from embassy"*).
  3. System creates `FollowUp` record with status `Pending`.
  4. When due timestamp arrives, system displays notification badge in rep inbox sidebar.
- **END STATE**: Follow-up task scheduled; reminder badge armed.
- **AUDIT EVENTS**: `FOLLOWUP_SCHEDULED`.
- **PERMISSION REQUIREMENTS**: `Lead:update`.

---

### Journey J7: Sales Rep Prepares & Dispatches a Quotation
- **START**: Matching vehicle sourced for a qualified lead.
- **ACTOR**: Sales Rep (`SalesAgent`) or Operations (`LogisticsAgent`).
- **TRIGGER**: Rep clicks "Generate Export Quote" on Lead card.
- **PRECONDITIONS**: Sourced vehicle selected; customer FCR eligibility known.
- **MAIN FLOW**:
  1. Rep enters vehicle base price in EUR and selects EU VAT regime (`Netto_Export`, `Brutto_Margin`).
  2. Rep enters transit insurance and shipping cost to destination port (Port of Rades / La Goulette).
  3. System auto-computes total EUR quote price and estimated Tunisia customs duties in TND (informational).
  4. Rep clicks "Generate PDF & Send Quote".
  5. System creates `Quotation` record (status `Sent`), renders styled PDF document, and dispatches message with PDF attachment to customer WhatsApp.
- **ALTERNATIVE FLOWS**:
  - High discount or margin override requested → System updates Quote status to `Draft (Pending Approval)` and notifies Manager (`TenantAdmin`). Manager approves → Rep dispatches quote.
- **ERROR CASES**:
  - PDF generation service fails → Display error alert; retain draft quote state.
- **END STATE**: PDF quote generated, stored in object storage, dispatched to customer; Lead state updated to `Quoted`.
- **AUDIT EVENTS**: `QUOTE_GENERATED`, `QUOTE_APPROVED` (if manager approval required), `QUOTE_DISPATCHED`.
- **PERMISSION REQUIREMENTS**: `Quotation:create`, `Quotation:view` (`Quotation:approve` for managers).

---

### Journey J8: Business Manager Reviews Sales Activity & Workload
- **START**: Business Owner / Manager logs into dashboard.
- **ACTOR**: Business Manager (`TenantAdmin`).
- **TRIGGER**: Manager accesses Operations Dashboard view.
- **PRECONDITIONS**: Manager authenticated with `TenantAdmin` role.
- **MAIN FLOW**:
  1. Manager views unassigned conversations queue, agent response latency, active lead pipeline stages, and pending quotes.
  2. Manager identifies unassigned high-priority chat and reassigns it to an available Sales Rep.
  3. Manager reviews high-value quote pending margin approval and clicks "Approve Quote".
- **END STATE**: Team workload rebalanced; pending quote authorized.
- **AUDIT EVENTS**: `CONVERSATION_REASSIGNED`, `QUOTE_APPROVED`.
- **PERMISSION REQUIREMENTS**: `User:view`, `Lead:assign`, `Quotation:approve`.

---

### Journey J9: Administrator Manages Users & Permissions
- **START**: Administrator needs to onboard a new sales team member.
- **ACTOR**: Tenant Administrator (`TenantAdmin`).
- **TRIGGER**: Admin accesses Settings → Team Management screen.
- **PRECONDITIONS**: Admin authenticated with `TenantAdmin` role.
- **MAIN FLOW**:
  1. Admin clicks "Invite Team Member".
  2. Admin enters user email, full name, and selects RBAC role (`SalesAgent`).
  3. System generates user invitation token and sends activation email.
  4. Admin deactivates an inactive former employee account.
- **END STATE**: User invited/deactivated; tenant directory updated.
- **AUDIT EVENTS**: `USER_INVITED`, `USER_DEACTIVATED`, `ROLE_CHANGED`.
- **PERMISSION REQUIREMENTS**: `User:invite`, `User:deactivate`, `User:change_role`.

---

### Journey J10: Employee Accesses Export Documents
- **START**: Sales or Operations rep needs to inspect vehicle export documents (*Carte Grise*, *FCR* certificate).
- **ACTOR**: Sales Rep (`SalesAgent`) or Operations Rep (`LogisticsAgent`).
- **TRIGGER**: Rep clicks on document attachment in Customer profile.
- **PRECONDITIONS**: Document uploaded and associated with customer under tenant context.
- **MAIN FLOW**:
  1. Rep clicks "View Document".
  2. System verifies user tenant matches document tenant.
  3. System generates short-lived pre-signed URL (15-minute expiry) to private object storage.
  4. Rep views secure document preview in browser modal.
- **ERROR CASES**:
  - User tenant does not match document tenant → Return HTTP 404 Not Found; log security audit alert.
- **END STATE**: Document securely viewed without exposing long-lived storage URLs.
- **AUDIT EVENTS**: `DOCUMENT_VIEWED`.
- **PERMISSION REQUIREMENTS**: `Document:view`.

---

## 4. WhatsApp Operational Inbox Workspace Workflow

The **WhatsApp Operational Inbox** is the primary workspace for sales representatives.

```text
+-----------------------------------------------------------------------------------+
|                               OPERATIONAL INBOX                                   |
+---------------------+-----------------------------------+-------------------------+
| CONVERSATION THREADS| ACTIVE CHAT WINDOW                | CUSTOMER & SOURCING CARD|
| [Search & Filters]  | Customer: Mohamed Ben Ali         | Name: Mohamed Ben Ali   |
| 🔴 PendingAgent (3) | +216 98 123 456                   | Phone: +216 98 123 456  |
| ------------------- | --------------------------------- | FCR Eligible: YES       |
| Mohamed Ben Ali     | [10:14] Customer:                 | ----------------------- |
| Golf 8 TDI FCR...   | Bonjour, je cherche Golf 8 TDI    | AI EXTRACTED REQUEST    |
| 10:14 AM            | 2021 budget 18000 €               | Make: Volkswagen        |
| ------------------- | --------------------------------- | Model: Golf 8           |
| Anis Khelifi        | [10:15] AI Suggestion (Draft):    | Fuel: Diesel (TDI)      |
| BMW X5 2020...      | "Bonjour Mohamed, nous avons      | Year: 2021+             |
| Yesterday           | plusieurs Golf 8 TDI disponibles  | Budget: €18,000         |
|                     | à partir de 17 500 € HT..."       | Status: QUALIFIED       |
|                     | [Edit]  [Approve & Send Message]  | [Generate Export Quote] |
+---------------------+-----------------------------------+-------------------------+
```

### Action Classification in Inbox:
- **SYSTEM ACTION**: Webhook reception, HMAC validation, message storage, pre-signed document URL generation.
- **AI ACTION**: Intent classification, parameter extraction into sidebar card, draft reply generation.
- **HUMAN ACTION**: Reviewing/editing extraction parameters, editing draft replies, clicking "Send", creating quotes.

---

## 5. Operational UX Principles

1. **Information Density**: Compact table rows, high-contrast status badges (`New`, `Qualified`, `Quoted`, `Won`), side-by-side chat and customer data cards.
2. **Zero AI-Slop Aesthetics**: No decorative background gradients, glowing borders, useless glassmorphism, or non-functional charts. Clean, dark/light balanced enterprise UI.
3. **Keyboard Accessibility**: Keyboard shortcuts (`Alt+N` for next thread, `Ctrl+Enter` to send message, `Esc` to close modal).
4. **Predictable Navigation**: Persistent top navigation bar (Inbox | Leads Pipeline | Inventory | Quotes | Settings).
