# ADR 0010: Idempotency and Optimistic Concurrency Control

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM processes state-mutating operations where duplicate executions or race conditions could cause severe business impact (e.g. Meta sending duplicate WhatsApp webhooks, sales reps double-clicking "Send Quote", or multiple reps simultaneously editing a Lead state).

We must define an HTTP-level idempotency key mechanism and an optimistic concurrency control strategy.

---

## 2. Decision Drivers

- **Zero Duplicate Financial Quotes / Outbound Messages**: Retried requests must safely return the original result without generating duplicate database records or sending duplicate WhatsApp messages.
- **Race Condition Defense**: Simultaneous updates to a Lead or Quotation must not silently overwrite concurrent employee changes (Lost Update problem).
- **Lightweight Infrastructure**: Mechanisms should leverage Redis and standard HTTP headers (`Idempotency-Key`, `If-Match`, `ETag`) without complex distributed locks.

---

## 3. Decision Outcome

**Chosen Option**: **`Idempotency-Key` HTTP Header for State-Mutating POST Operations** paired with **ETag / Version-Based Optimistic Concurrency Control for Mutable Resources**.

### Specifications:

#### 1. Idempotency Key Specification:
- Supported Endpoints: `POST /api/v1/conversations/{id}/messages`, `POST /api/v1/quotes`, `POST /api/v1/documents/upload-intent`.
- **Header**: `Idempotency-Key: <uuidv4_or_unique_string>`
- **Behavior**:
  1. API gateway/middleware checks Redis key `idempotency:<tenant_id>:<key>`.
  2. If key exists and status is `COMPLETED`, immediately return cached response envelope with `X-Cache-Lookup: HIT`.
  3. If key exists and status is `PROCESSING`, return `HTTP 409 Conflict` (`CONCURRENT_REQUEST_IN_PROGRESS`).
  4. If key does not exist, set status `PROCESSING` with 60-second TTL, execute transaction, cache final response with 24-hour TTL, and return.
- **Meta WhatsApp Webhook Idempotency**: Deduplicated automatically using Meta `wamid` stored in `messages.provider_message_id` with `UNIQUE (tenant_id, provider_message_id)` constraint (`BR-008`).

#### 2. Optimistic Concurrency Control (OCC):
- Supported Resources: `Lead`, `Quotation`, `Customer`.
- Resource representations include an opaque `version` or `updated_at` ETag timestamp string (e.g. `ETag: "W/\"018f4b29-v2\""`).
- State-mutating `PATCH` / `PUT` requests accept `If-Match: "W/\"018f4b29-v2\""`.
- If database version does not match `If-Match`, the update is aborted and returns `HTTP 409 Conflict` (`CONCURRENCY_CONFLICT`).

---

## 4. Consequences

### Positive:
- Total protection against duplicate quote generation and duplicate WhatsApp dispatches.
- Prevents silent lost updates when multiple sales reps collaborate in the inbox workspace.
- Standard HTTP header compliance.

### Negative / Mitigation:
- Requires Redis storage for 24-hour idempotency key cache. (Minimal memory footprint; automatically pruned by Redis TTL).
