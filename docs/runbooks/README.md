# Car-Export-CRM Operational Runbooks (`RB-001` – `RB-012`)

This directory contains the 12 production operational runbooks for managing deployment, rollback, schema evolution, disaster recovery, queue failover, database recovery, third-party outages, credential rotation, security containment, and file quarantine for the **Car-Export-CRM** platform (`docs/infrastructure-architecture.md` Section 29).

---

## Operational Runbooks Index

| Runbook ID | Runbook Title | Target Component | Document File |
| :--- | :--- | :--- | :--- |
| **`RB-001`** | Application Deployment & Zero-Downtime Release | CI/CD & ECS Compute | [`RB-001-deployment-and-release.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/runbooks/RB-001-deployment-and-release.md) |
| **`RB-002`** | Deployment Rollback Procedure | ECS Compute & Image Tags | [`RB-002-deployment-rollback.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/runbooks/RB-002-deployment-rollback.md) |
| **`RB-003`** | Expand-Migrate-Contract DB Schema Evolution | Alembic & PostgreSQL | [`RB-003-db-schema-evolution.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/runbooks/RB-003-db-schema-evolution.md) |
| **`RB-004`** | PostgreSQL Backup Restoration (PITR Drill) | PostgreSQL & S3 WAL | [`RB-004-pitr-backup-restoration.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/runbooks/RB-004-pitr-backup-restoration.md) |
| **`RB-005`** | Background Worker Queue Recovery & Reconciliation | Redis ARQ & Worker | [`RB-005-worker-queue-recovery.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/runbooks/RB-005-worker-queue-recovery.md) |
| **`RB-006`** | Redis Store Failover & Reconciliation Re-enqueue | Redis Cache & ARQ | [`RB-006-redis-failover-reconciliation.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/runbooks/RB-006-redis-failover-reconciliation.md) |
| **`RB-007`** | PostgreSQL Failover & Connection Pool Reset | Async Engine Pool | [`RB-007-postgres-failover.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/runbooks/RB-007-postgres-failover.md) |
| **`RB-008`** | Meta WhatsApp Webhook Ingestion Outage Recovery | WhatsApp BSP Router | [`RB-008-whatsapp-outage-recovery.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/runbooks/RB-008-whatsapp-outage-recovery.md) |
| **`RB-009`** | LLM Provider Outage & Circuit Breaker Reset | AI Provider Port | [`RB-009-llm-outage-circuit-breaker.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/runbooks/RB-009-llm-outage-circuit-breaker.md) |
| **`RB-010`** | Security Credential & API Key Rotation | Secrets Manager / Auth | [`RB-010-credential-api-key-rotation.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/runbooks/RB-010-credential-api-key-rotation.md) |
| **`RB-011`** | Security Incident & Account Suspension Isolation | Multi-Tenant Scoping | [`RB-011-security-incident-containment.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/runbooks/RB-011-security-incident-containment.md) |
| **`RB-012`** | Document Malware Quarantine & Scan Error Resolution | S3 Object Bucket | [`RB-012-document-malware-quarantine.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/runbooks/RB-012-document-malware-quarantine.md) |
