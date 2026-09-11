# ADR 0013: Multi-Tenant Security Invariants and IDOR Defense

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM is a multi-tenant B2B SaaS platform where multiple independent car export businesses share common infrastructure. 

A primary security threat is horizontal privilege escalation and Insecure Direct Object Reference (IDOR / BOLA), where an attacker from Tenant A attempts to access or mutate resources belonging to Tenant B by guessing or manipulating resource IDs. We must establish non-negotiable security invariants and database/API enforcement rules.

---

## 2. Decision Drivers

- **Zero Cross-Tenant Data Leakage**: Absolute security boundary preventing cross-tenant reads or writes.
- **Enumeration & Disclosure Prevention**: Accessing another tenant's resource must NOT disclose whether the resource exists. Non-sequential UUIDv7 identifiers reduce predictable enumeration, but provide NO authorization boundary by themselves.
- **Context Authority**: Trusted server-side authenticated application context is the ONLY source of tenant identity (`BR-001`). Client input is never trusted.

---

## 3. Decision Outcome

**Chosen Option**: **11 Mandatory Multi-Tenant Security Invariants (`SEC-001` to `SEC-011`) + 404 Response Disclosure Prevention**.

### 11 Mandatory Security Invariants:
1. **`SEC-001` (Tenant Context Source)**: Tenant context MUST derive strictly from authenticated server-side identity/token claims (`BR-001`).
2. **`SEC-002` (Client Non-Trust)**: Client input (URL params, request body, query strings) MUST NEVER establish or override tenant scope.
3. **`SEC-003` (Database Query Boundary)**: Every database query on tenant-owned tables MUST explicitly enforce `.where(Model.tenant_id == current_tenant_id)` (`BR-002`).
4. **`SEC-004` (Async Worker Context)**: Background jobs (Redis/ARQ) MUST carry explicit, authenticated `tenant_id` context (`BR-001`).
5. **`SEC-005` (Cache Keyspace Isolation)**: Redis cache keys MUST include `tenant_id` namespace prefixes (e.g. `cache:<tenant_id>:<key>`).
6. **`SEC-006` (Object-Storage Authorization)**: S3 object access MUST be tenant-authorized before pre-signed URL generation.
7. **`SEC-007` (Vector / RAG Isolation)**: Vector similarity searches MUST include `WHERE tenant_id = :current_tenant_id` in SQL queries (`ADR 0011`).
8. **`SEC-008` (AI Prompt Isolation)**: Cross-tenant data must NEVER enter an LLM prompt or RAG context.
9. **`SEC-009` (Audit Log Attribution)**: Every security event and data mutation MUST record `tenant_id` and `user_id`.
10. **`SEC-010` (Disclosure Defense)**: Unauthorized cross-tenant resource requests MUST return `HTTP 404 Not Found` instead of `403 Forbidden` to hide resource existence (`BR-002`, `AC-01`).
11. **`SEC-011` (Authenticated Job Context)**: Every asynchronous job must contain validated tenant and operation context derived from a trusted application transaction. Workers MUST NOT derive authorization solely from user-controlled job payload data.

---

## 4. Consequences

### Positive:
- Total defense against IDOR/BOLA attacks.
- Hides resource existence from cross-tenant probing attacks.
- Enforces strict security boundary for asynchronous background workers.
- Standardized, automated security contract across all API endpoints and repositories.

### Negative / Mitigation:
- Requires strict developer discipline and automated integration tests (`AC-01`) verifying 404 responses for cross-tenant IDs.
