# ADR 0008: API Versioning and Response Envelope Specification

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM requires a clean, consistent REST API design for client-server communication between the React B2B Inbox frontend, background workers, and external webhooks.

We must define the URL versioning strategy, standard JSON response envelopes, error response formats, and date/time/identifier serialization standards.

---

## 2. Decision Drivers

- **Predictability & Consistency**: Every REST API endpoint must return standardized JSON payloads.
- **Client Developer Ergonomics**: Clear separation between success envelopes and RFC 7807 problem details error structures.
- **Future Extensibility**: Seamless handling of future API version changes without breaking existing client integrations.
- **Zero Ambiguity for Data Types**: ISO-8601 UTC strings for timestamps, UUIDv7 strings for IDs, exact decimal representations for currency.

---

## 3. Considered Options

### Versioning:
1. **Option 1**: URI Path Versioning (`/api/v1/...`).
2. **Option 2**: HTTP Header Versioning (`Accept: application/vnd.car-export-crm.v1+json`).
3. **Option 3**: Query Parameter Versioning (`/api/customers?version=1`).

### Response Envelopes:
1. **Option A**: Bare Resource Payloads (Direct JSON objects without wrapper).
2. **Option B**: Standardized Envelopes (`{ "success": true, "data": ..., "meta": ... }` for success; RFC 7807 for errors).

---

## 4. Decision Outcome

**Chosen Option**: **URI Path Versioning (`/api/v1/...`)** paired with **Standardized JSON Response Envelopes**.

### Specifications:

#### 1. Versioning:
- All core API endpoints reside under `/api/v1/`.
- Breaking changes require a new URI prefix (`/api/v2/`). Adding optional response fields or optional query parameters is classified as a non-breaking change.

#### 2. Success Response Envelope:
```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "timestamp": "2026-09-11T15:00:00Z",
    "correlation_id": "req-8f4b29a1-09bc"
  }
}
```

#### 3. Error Response Envelope (RFC 7807 Problem Details):
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Vehicle request parameters failed schema validation.",
    "details": [
      {
        "field": "budget_eur",
        "issue": "Must be a positive decimal number."
      }
    ],
    "timestamp": "2026-09-11T15:00:00Z",
    "correlation_id": "req-8f4b29a1-09bc"
  }
}
```

#### 4. Serialization Conventions:
- **Identifiers**: 36-character hyphenated UUIDv7 string (`018f4b29-a109-7bc3-89bd-2b0d7b3dcb6d`).
- **Timestamps**: ISO-8601 UTC string (`YYYY-MM-DDTHH:MM:SSZ`).
- **Currency/Monetary Values**: String or fixed-precision number formatted to 2 decimal places in EUR or 3 in TND (e.g. `18500.00`). Floating-point approximations are strictly forbidden.

---

## 5. Consequences

### Positive:
- Highly predictable contracts across all application modules.
- RFC 7807 compliance simplifies frontend form field error highlighting.
- Clean separation between success envelopes and error states.

### Negative / Mitigation:
- Minimal payload size overhead from wrapper envelopes. (Negligible impact over HTTP/2 gzip/brotli compression).
