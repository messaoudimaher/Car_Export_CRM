---
name: backend
description: >-
  Use this skill when developing FastAPI endpoints, writing SQLAlchemy async queries, creating background workers, building service layers, or implementing API error handling.
---

# Backend Engineering Skill

## 1. Purpose & Scope
Provide standards and procedural guidance for Python 3.11+, FastAPI controllers, async SQLAlchemy 2.0 ORM queries, background worker jobs, and REST API controllers.

## 2. Activation Triggers
Activate when implementing backend REST endpoints, database queries, service modules, background worker tasks, or API error handlers.

## 3. Inspection Targets
- [`DEVELOPMENT.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/DEVELOPMENT.md) (Python standards & type safety)
- [`docs/api-contracts.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/api-contracts.md) (REST envelope & RFC 7807 problem details)
- [`SECURITY.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/SECURITY.md) (Tenant context & parameterized query rules)

## 4. Constraints
- **Strict Tenant Filtering**: Every database model query MUST include `.where(Model.tenant_id == current_tenant_id)`.
- **Async Task Offloading**: Webhook handlers MUST NOT run heavy computations inline; enqueue jobs to Redis task queue and return immediately.
- **REST Envelopes**: All controller outputs MUST be wrapped in standard envelopes (`success`, `data`, `meta`, `error`).
- **Strict Typing**: All functions, parameters, and returns MUST have explicit type annotations. Pass `mypy src/backend --strict` with zero errors.

## 5. Execution Procedure
1. Create Pydantic v2 request/response schemas.
2. Implement FastAPI route handler with explicit status code and dependency-injected session/context.
3. Implement service layer method enforcing business rules and tenant filtering.
4. Add structured JSON log output containing `correlation_id` and `tenant_id`.

## 6. Expected Outputs
- Fully typed Python/FastAPI endpoints and services.
- Clean Pydantic schemas and standard REST envelopes.
