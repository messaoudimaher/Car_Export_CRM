# ADR 0009: Cursor Pagination and Filter Whitelist Strategy

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM handles high-volume messaging threads (hundreds of thousands of WhatsApp messages), fast-changing conversation lists, and audit event streams.

Traditional offset-based pagination (`OFFSET 1000 LIMIT 25`) degrades significantly in PostgreSQL as offsets increase, causes missed/duplicate items when real-time messages arrive during scrolling, and exposes internal database query structures. We need a performant, stable pagination and filtering strategy.

---

## 2. Decision Drivers

- **High-Volume Real-Time Performance**: Fast scrolling in WhatsApp chat history and inbox threads without `OFFSET` table scan overhead.
- **Data Stability**: Page boundaries must not drift when new incoming WhatsApp webhooks insert items at the top of the feed.
- **SQL Injection & Resource Exhaustion Defense**: Filtering and sorting must be strictly whitelisted per endpoint to prevent arbitrary query injection or unbounded CPU spikes.

---

## 3. Decision Outcome

**Chosen Option**: **Opaque Base64 Cursor Pagination for High-Volume Feeds** paired with **Strict Whitelisted Filtering & Sorting Parameters**.

### Specifications:

#### 1. Cursor Pagination Protocol (Messages, Conversations, Audit Logs):
- **Request Parameters**:
  - `cursor`: Opaque base64 encoded string encoding `(created_at, id)` pointer.
  - `limit`: Integer between 1 and 100 (Default: `25`).
- **Response `meta` Pagination Envelope**:
  ```json
  "meta": {
    "limit": 25,
    "has_next": true,
    "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNi0wOS0xMVQxNDowMDowMFoiLCJpZCI6IjAxOGY0YjI5LWExMDktN2JjMy04OWJkLTJiMGQ3YjNkY2I2ZCJ9",
    "total": 1420
  }
  ```

#### 2. Filtering Whitelist Enforcement:
- Arbitrary SQL-like query parameters (e.g. `?where=age>5`) are strictly forbidden.
- Each endpoint defines an explicit whitelist of supported query filters:
  - `GET /api/v1/conversations`: `status` (`PendingAgent`, `Active`, `Resolved`), `assigned_agent_id` (`unassigned`, `<uuid>`), `search` (phone/name trigram).
  - `GET /api/v1/leads`: `status` (`New`, `Qualified`, `Sourcing`, `Quoted`, `Won`, `Lost`), `assigned_agent_id`, `priority`.
  - `GET /api/v1/vehicles`: `make`, `model`, `max_price_eur`, `vat_regime`, `fcr_eligible`.
- Unrecognized or non-whitelisted query parameters trigger `HTTP 400 Bad Request`.

#### 3. Sorting Whitelist Enforcement:
- Sort field selection is restricted to pre-indexed table columns via `sort_by`:
  - Format: `sort_by=-created_at` (Descending) or `sort_by=created_at` (Ascending).

---

## 4. Consequences

### Positive:
- $O(1)$ query execution time regardless of pagination depth.
- Zero missed or duplicated messages when scrolling active WhatsApp chat threads.
- Strong security defense against SQL injection and resource exhaustion attacks.

### Negative / Mitigation:
- Clients cannot jump directly to an arbitrary page number (e.g. "Page 42"). (Mitigated because messaging and CRM workflows use infinite scrolling or date filtering).
