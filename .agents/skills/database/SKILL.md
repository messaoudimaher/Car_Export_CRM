---
name: database
description: >-
  Use this skill when designing PostgreSQL schemas, creating Alembic migrations, optimizing query performance, indexing multi-tenant columns, or managing database seeds.
---

# Database Engineering & Migration Skill

## 1. Purpose & Scope
Guide PostgreSQL schema design, multi-tenant row-level indexing strategies, Alembic migration scripts, and SQLAlchemy ORM model definitions.

## 2. Activation Triggers
Activate when creating or modifying database models, generating Alembic migrations, adding indexes, or optimizing database query performance.

## 3. Inspection Targets
- [`docs/domain-model.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/domain-model.md) (Domain entity models & relationships)
- [`SECURITY.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/SECURITY.md) (Multi-tenant database query constraints)

## 4. Constraints
- **Multi-Tenant Column Rule**: Every tenant-owned table MUST contain `tenant_id: UUID (NOT NULL, FK to tenants.id)`.
- **Indexing Rule**: High-volume tables (`messages`, `leads`, `customers`) MUST have compound indexes on `(tenant_id, created_at)` and `(tenant_id, status)`.
- **Migration Discipline**: Every schema change MUST include an explicit Alembic migration script with both `upgrade` and `downgrade` functions tested.

## 5. Execution Procedure
1. Define SQLAlchemy 2.0 Mapped model with explicit types and foreign keys.
2. Add compound indexes for multi-tenant query patterns.
3. Generate Alembic migration: `alembic revision --autogenerate -m "add_table_name"`.
4. Review generated migration file and verify clean rollback behavior.

## 6. Expected Outputs
- Validated SQLAlchemy model class.
- Clean Alembic migration script tested for upgrade/downgrade.
