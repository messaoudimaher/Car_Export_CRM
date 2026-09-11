# PRODUCT.md - Product Requirements Document (PRD)

## 1. Product Vision & Problem Statement

**Car-Export-CRM** is a specialized, multi-tenant B2B Customer & Export Management Platform built for automotive export companies operating between **Europe** (Germany, France, Italy, Belgium, Netherlands) and **Tunisia**.

### Core Problem:
Cross-border vehicle sales to Tunisian buyers (individual expatriates returning via FCR privileges, local brokers, or private buyers) occur almost exclusively via **WhatsApp**. Exporters manage hundreds of unorganized chats, resulting in lost inquiries, forgotten follow-ups, miscalculated export VAT/customs fees, and delayed quotes. Traditional CRMs fail because sales reps dislike manual data entry outside messaging apps.

### Core Product Promise:
> *"Never lose a customer because of a missed WhatsApp message."*

---

## 2. Target Market, User Personas & RBAC Model

### 2.1 Target Exporter Profile
Small to medium European car export businesses (1–25 employees) sourcing vehicles in Germany, France, or Italy and exporting to Tunisian buyers at ports of Rades and La Goulette.

### 2.2 Primary User Personas

#### 1. Business Owner / Manager
- **Goals**: Maximize lead conversion rate, ensure zero dropped inquiries, monitor sales pipeline value, and audit quote accuracy.
- **Responsibilities**: Oversee sales reps, review high-value quotes, set pricing markup margins, review tenant performance reports.
- **Actions**: Assign leads/chats, approve high-discount quotes, manage team members, access tenant settings.

#### 2. Sales Employee (Sales Rep)
- **Goals**: Respond rapidly to WhatsApp inquiries, qualify buyer intent, select matching sourced vehicles, generate formal export quotes, and close deals.
- **Responsibilities**: Manage assigned WhatsApp conversations, review AI-extracted vehicle requests, send AI-assisted or custom responses, schedule follow-ups.
- **Actions**: Send WhatsApp messages, edit AI draft responses, create/edit vehicle requests, generate quotes, update lead status, set follow-up reminders.

#### 3. Operations / Sourcing Employee
- **Goals**: Source matching vehicles across European suppliers, calculate accurate European export VAT (Netto/Brutto), verify Tunisia FCR eligibility, estimate customs duties, and track export documentation.
- **Responsibilities**: Manage vehicle inventory records, attach sourcing options to vehicle requests, compute shipping/insurance costs, verify *Carte Grise* and *FCR* certs.
- **Actions**: Add vehicle records, attach vehicle matches to leads, generate shipping estimates, upload export docs.

#### 4. Administrator (Tenant Admin)
- **Goals**: Maintain tenant infrastructure, manage user accounts, configure WhatsApp API channels, set role permissions, audit security logs.
- **Responsibilities**: User provisioning, WhatsApp integration key management, tenant profile configuration.
- **Actions**: Invite/disable users, update tenant profile, configure WhatsApp webhooks, view audit logs.

### 2.3 Conceptual RBAC Permission Matrix

| Resource | Action | SuperAdmin | TenantAdmin | SalesAgent | LogisticsAgent |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Customer** | `view`, `create`, `update` | Yes | Yes | Yes | Yes |
| **Customer** | `delete` | Yes | Yes | No | No |
| **Conversation** | `view`, `assign`, `respond`, `resolve` | Yes | Yes | Yes (Assigned/Unassigned) | View Only |
| **Lead** | `view`, `create`, `update`, `assign` | Yes | Yes | Yes (Assigned) | View Only |
| **Vehicle** | `view`, `create`, `update` | Yes | Yes | View Only | Yes |
| **Quotation** | `view`, `create` | Yes | Yes | Yes | Yes |
| **Quotation** | `approve` (Margin Overrides) | Yes | Yes | No | No |
| **Document** | `view`, `upload` | Yes | Yes | Yes | Yes |
| **Document** | `delete` | Yes | Yes | No | No |
| **User Management** | `view`, `invite`, `deactivate`, `change_role` | Yes | Yes | No | No |
| **Audit Logs** | `view` | Yes | Yes | No | No |

### 2.4 Fundamental Tenant Security Invariant
- **Tenant Context Authority**: Tenant context MUST ALWAYS be derived from authenticated identity tokens (JWT or server-side session).
- **Client Non-Trust**: NEVER accept `tenant_id` from client-controlled parameters (URL query params, JSON payload, client headers).
- **Database Query Filtering**: Every database model query MUST include an explicit `where(Entity.tenant_id == current_tenant_id)` clause.

---

## 3. Core Customer Journey & Specifications

- Detailed step-by-step user journeys (J1 through J10), flowcharts, error handling, and audit triggers are documented in [`docs/user-journeys.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/user-journeys.md).
- Complete ID-based functional requirements (FR-*), business rules (BR-*), acceptance criteria, and traceability matrices are documented in [`docs/functional-requirements.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/functional-requirements.md).
- Refined domain specs, aggregates, value objects, invariants (INV-*), and conceptual domain events are documented in [`docs/domain-model.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/domain-model.md).

```text
Inbound WhatsApp Message 
  ↳ 1. Automated Webhook Ingestion & Customer Matching
    ↳ 2. Conversation Threading & Unassigned Queue
      ↳ 3. AI Intent Detection & Vehicle Request Parameter Extraction
        ↳ 4. Qualified Lead Creation & Sales Rep Assignment
          ↳ 5. Operations Vehicle Sourcing Match (Netto/Brutto VAT + FCR Check)
            ↳ 6. Sales Rep Review of AI Suggested Response & Draft Quote
              ↳ 7. Customer Presentation & WhatsApp Quotation Dispatch
                ↳ 8. Scheduled Follow-up Tracking & Reminder Notifications
                  ↳ 9. Deal Close (Won / Lost) & Export Document Archival
```

---

## 4. Product Principles

1. **WhatsApp-Native Execution**: Sales reps manage everything directly within the unified WhatsApp inbox workspace.
2. **AI as Assistant, Human as Authority**: AI handles parsing, summarization, and draft generation. Humans authorize all prices, availability, quotes, and customer communications.
3. **Operational Density**: UI prioritizes fast scanning, search, keyboard shortcuts, and clear status badges over empty decorative whitespace or generic charts.
4. **Export Domain Integrity**: Built-in understanding of European Netto/Brutto VAT, Tunisia FCR 5-year age limits, and port logistics (Rades / La Goulette).

---

## 5. MVP Scope Categorization

### 5.1 MUST HAVE (Core MVP Scope)
- **Multi-Tenant Foundation**: Secure tenant context, user authentication, RBAC roles.
- **WhatsApp Integration**: Webhook ingestion, outbound message dispatch, text and image support.
- **Unified Inbox Workspace**: 3-panel layout (Conversations List | Chat Thread | Customer & Sourcing Sidebar).
- **Customer Directory**: Customer profiles, phone numbers (E.164), FCR eligibility status, notes.
- **AI Understanding Engine**: Intent detection, parameter extraction (Make, Model, Year, Fuel, Budget, FCR), summary generation.
- **Vehicle Request & Lead Pipeline**: Lead states (`New`, `Qualified`, `Sourcing`, `Quoted`, `Won`, `Lost`), vehicle request criteria.
- **Export Quotation Generator**: Price breakdown (Vehicle price, EU VAT regime, transit insurance, shipping, estimated Tunisia customs), PDF export generation.
- **Follow-up Reminders**: Scheduled follow-up timestamps, reminder badges in inbox.
- **Basic Document Management**: Upload and attachment of vehicle photos, *Carte Grise*, and PDF quotes.
- **Security & Audit Foundations**: Multi-tenant row-level isolation, audit event logging, PII protections.

### 5.2 SHOULD HAVE (Post-MVP Enhancements)
- WhatsApp Template Message Manager & Interactive Buttons.
- Voice note audio transcription (Whisper integration).
- Automated European marketplace search scrapers (Mobile.de, AutoScout24 links).
- Customer self-service quote status tracking link.

### 5.3 LATER (Future Roadmap)
- Multi-channel support (Facebook Messenger, Instagram DMs).
- Advanced analytics reporting (conversion funnel speed, agent performance metrics).
- Multi-currency automatic FX conversion rate updater.

### 5.4 EXCLUDED FROM MVP (Strictly Out of Scope)
- Accounting / Double-entry general ledger ERP.
- Online payment gateway processing / Credit card processing / Crypto payments.
- Live vessel shipping telemetry / GPS tracking.
- Autonomous AI purchasing / Autonomous unvetted chat bots.
- Mobile native application (React Native / iOS / Android apps).
- Microservices infrastructure / Service mesh / Kubernetes setups.

---

## 6. Major Business Objects Overview

Full specifications, value objects, aggregate boundaries, invariants (`INV-*`), and events for all 13 core business objects are defined in [`docs/domain-model.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/domain-model.md):

1. **`Tenant`**: Root organizational account (e.g. "AutoExport Hamburg GmbH"). Owns all data.
2. **`User`**: Exporter employee (Business Owner, Sales Rep, Operations, Admin).
3. **`Customer`**: Buyer in Tunisia or broker profile (`phone_number`, `fcr_eligible`).
4. **`WhatsAppConversation`**: Active chat thread context with status (`Active`, `PendingAgent`, `Resolved`, `Archived`).
5. **`Message`**: Inbound or outbound text/media payload (`wamid`, `direction`, `content`).
6. **`AIUnderstanding`**: Extracted intent, parameter payload, and confidence scores.
7. **`VehicleRequest`**: Structured customer criteria (Make, Model, Min Year, Fuel, Budget, FCR required).
8. **`Lead`**: Sales opportunity card tracking pipeline state (`New` → `Qualified` → `Sourcing` → `Quoted` → `Won`/`Lost`).
9. **`Vehicle`**: Vehicle stock or sourced item details (VIN, Price, EU VAT status, location).
10. **`Quotation`**: Formal export quote document (`quote_number`, vehicle price, shipping, estimated customs, total).
11. **`FollowUp`**: Scheduled rep reminder (`due_at`, `status`, `notes`).
12. **`Document`**: File metadata and storage reference (*Carte Grise*, *FCR* cert, Quote PDF).
13. **`AuditEvent`**: Immutably logged system action (`user_id`, `action`, `timestamp`).

---

## 7. AI Boundaries & Guardrails

### 7.1 Allowed AI Capabilities:
- Intent classification (`SourcingInquiry`, `PriceCheck`, `CustomsFCRInquiry`, `ShippingStatus`).
- Parameter extraction into Pydantic models.
- Multilingual translation between French, Arabic (Tunisian Darija), and English.
- Generating draft message responses for sales rep review.
- Summarizing long WhatsApp conversation histories.

### 7.2 Forbidden AI Actions (Requires Human Explicit Action):
- AI MUST NOT send unvetted automated messages to customers.
- AI MUST NOT commit the business to vehicle prices, discounts, or payment terms.
- AI MUST NOT confirm vehicle availability or reservation.
- AI MUST NOT guarantee shipping delivery dates or Tunisia customs clearance.
- AI MUST NOT issue binding financial quotes or legal export contracts.

---

## 8. Multilingual Strategy

- **French (`fr`)**: **Required**. Primary UI language, PDF quote language, and formal customer communication language.
- **Tunisian Arabic (`ar_TN`)**: **Supported via AI Parsing**. Customer inbound messages written in Romanized Darija (e.g. *"nhebb Golf 8 mazout FCR"*) or Arabic script are parsed by the AI extraction layer into standard French summary objects for sales reps.
- **English (`en`)**: **Desirable / Secondary**. Supported for European supplier communications and secondary UI display.

---

## 9. Measurable MVP Success Criteria

1. **Message Retention**: 100% of inbound WhatsApp messages are successfully captured and attached to customer threads without message loss.
2. **Speed to Response**: Average time from inbound customer message to rep response reduced by 50% via AI draft suggestions.
3. **Extraction Accuracy**: > 90% accuracy on vehicle parameter extraction (Make, Model, Budget, FCR) verified against manual rep corrections.
4. **Zero Cross-Tenant Leakage**: 100% pass rate on cross-tenant boundary security tests.
5. **Human Authority Compliance**: 0% unvetted automated messages sent to customers; 100% of quotes explicitly approved by reps.

---

## 10. Future Roadmap (Post-MVP)

- **Phase 1 (MVP)**: WhatsApp Inbox, AI extraction, Lead pipeline, Export Quote PDF generator, Multi-tenant security foundation.
- **Phase 2**: Automated Mobile.de & AutoScout24 sourcing links, WhatsApp template manager, voice note transcription.
- **Phase 3**: Custom export workflow pipelines for other North African markets (Algeria, Morocco), advanced analytics reporting.
