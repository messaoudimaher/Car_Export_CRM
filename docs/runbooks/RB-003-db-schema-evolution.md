# RB-003: Expand-Migrate-Contract DB Schema Evolution & Recovery Runbook

**Runbook ID**: `RB-003`  
**Target Component**: Alembic & PostgreSQL Database  
**Severity Level**: Standard / Medium (P2)  
**Execution Trigger**: Database schema migrations modifying existing tables or column definitions  

---

## 1. Objective & Scope

Governs backward-compatible database schema evolution using the 3-phase **Expand-Migrate-Contract** pattern (`ADR 0017`).

---

## 2. The 3-Phase Evolution Strategy

1. **Phase 1: Expand (Release N)**:
   - Add new nullable columns or new tables. Old application version N continues using old columns seamlessly.
2. **Phase 2: Migrate (Release N+1)**:
   - Deploy code N+1 reading from new columns and writing to both old and new columns. Run background data backfill script.
3. **Phase 3: Contract (Release N+2)**:
   - Drop old deprecated columns in a future release once N+1 code is 100% stable.

---

## 3. Migration Recovery & Advisory Lock Procedures

- **Advisory Lock Check**: Alembic uses PostgreSQL `pg_advisory_xact_lock` to prevent multi-container migration race conditions.
- **Blocked Migration Resolution**:
   ```sql
   -- Inspect active lock processes
   SELECT pid, query, age(clock_timestamp(), query_start) FROM pg_stat_activity WHERE query LIKE '%alembic%';
   -- Terminate hung migration lock PID
   SELECT pg_terminate_backend(<PID>);
   ```
