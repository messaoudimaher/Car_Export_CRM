# ADR 0001: Modular Monolith Architecture Baseline

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM requires a clean, robust, and scalable backend architecture to handle WhatsApp message ingestion, customer management, AI extraction, vehicle sourcing, and quotation workflows. 

We need an architecture that supports fast MVP velocity, low operational overhead, simple multi-tenant data isolation, and strong module boundaries, without premature distributed systems complexity.

---

## 2. Decision Drivers

- **Speed of MVP Delivery**: High developer velocity with minimal infrastructure setup.
- **Strict Domain Boundaries**: Clear separation between Messaging, Customers, Sourcing, Quotes, and AI modules.
- **Operational Simplicity**: Single deployment unit for backend server and worker binaries.
- **Future Extensibility**: Ability to split individual modules into independent microservices in the future if scale requires it.

---

## 3. Considered Options

1. **Option 1**: Microservices Architecture (Separate services for Webhook, Messaging, CRM, Quotes, AI).
2. **Option 2**: Spaghetti Monolith (Single backend without internal module boundaries).
3. **Option 3**: Modular Monolith + Asynchronous Workers (FastAPI, SQLAlchemy, Redis background tasks, clean module boundaries).

---

## 4. Decision Outcome

**Chosen Option**: **Option 3: Modular Monolith + Asynchronous Workers**.

### Positive Consequences:
- Single codebase with strict internal module boundaries (`app/modules/messaging`, `app/modules/customers`, `app/modules/quotes`).
- Shared PostgreSQL database with explicit multi-tenant `tenant_id` row-level isolation.
- Asynchronous task processing (Redis + worker background queue) handles heavy webhooks, LLM calls, and PDF rendering without blocking HTTP endpoints.
- Port and Adapter abstraction ensures external services (WhatsApp, OpenAI, S3) can be mocked or swapped cleanly.

### Negative Consequences / Mitigation:
- Requires strict discipline to prevent cross-module direct database table joins. (Mitigation: Modules interact through public domain service interfaces or async event handlers).
