# ADR 0006: Tenant Isolation & Multi-Tenancy Database Strategy

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM is a multi-tenant platform where separate car export companies share system infrastructure. 

A fundamental security invariant (`INV-001`, `BR-002`) dictates that a user or background job from Tenant A must NEVER be able to read, mutate, or expose data belonging to Tenant B. We must define the physical storage strategy and database enforcement mechanism for tenant isolation.

---

## 2. Decision Drivers

- **Security & Data Isolation**: Zero cross-tenant data leakage under any scenario.
- **Operational Complexity & Cost**: Multi-tenant database per tenant or schema per tenant creates massive schema migration and connection pool overhead for hundreds of small export agencies.
- **Async Background Worker Compatibility**: Async background tasks (ARQ / Redis) must reliably propagate tenant context without connection session leakage.
- **Query Performance**: Indexing strategies must optimize queries filtered by tenant.

---

## 3. Considered Options

1. **Option 1**: Database-per-Tenant (Separate PostgreSQL database per tenant).
2. **Option 2**: Schema-per-Tenant (Separate PostgreSQL schema per tenant in one database).
3. **Option 3**: Discriminator Column (`tenant_id`) with PostgreSQL Row-Level Security (RLS).
4. **Option 4**: Discriminator Column (`tenant_id`) with Application-Level Enforcement + Composite Foreign Keys & Unique Constraints.

---

## 4. Decision Outcome

**Chosen Option**: **Option 4: Discriminator Column (`tenant_id`) with Application-Level Context Enforcement + Composite Database Constraints**.

### Rationale:
- **Database-per-Tenant / Schema-per-Tenant**: Rejected for MVP due to extreme migration overhead, complex connection pooling with FastAPI/SQLAlchemy, and high cost for small 1–25 person export teams.
- **PostgreSQL RLS**: Evaluated thoroughly. While RLS provides DB-level policy enforcement, setting `SET LOCAL app.current_tenant_id` on pooled connections in an asynchronous Python environment (`asyncpg` + SQLAlchemy 2.0 async session) introduces severe risks of connection state bleeding if a connection isn't properly reset between async tasks.
- **Application-Level Enforcement + Composite Constraints**:
  - Every tenant-owned table contains `tenant_id: UUID NOT NULL REFERENCES tenants(id)`.
  - Every query is strictly filtered by `tenant_id` derived from authenticated JWT claims (`BR-001`).
  - Database schema enforces tenant-scoped composite unique constraints (e.g. `UNIQUE (tenant_id, phone_e164)`, `UNIQUE (tenant_id, provider_message_id)`).
  - High-volume queries use composite indexes prefixed with `tenant_id` (e.g. `(tenant_id, created_at)`).

### Compensating Controls:
1. **Repository Base Boundary**: Centralized SQLAlchemy repository base class automatically appends `.where(Model.tenant_id == current_tenant_id)` to all select/update/delete statements.
2. **Mandatory Security Integration Tests**: Automated test suite (`AC-01`) tests every API endpoint with cross-tenant IDs, asserting `404 Not Found`.
3. **IDOR Defense**: All resource URLs use un-enumerable UUIDv7 primary keys.

---

## 5. Consequences

### Positive:
- Simple, high-performance single-database deployment.
- Clean connection pooling and migration management via Alembic.
- Strong protection against cross-tenant collisions via composite unique constraints.

### Negative / Mitigation:
- Relies on application code discipline. (Mitigated by mandatory repository base class enforcement and security test suites).
