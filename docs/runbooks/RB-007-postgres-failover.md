# RB-007: PostgreSQL Failover & Connection Pool Reset Runbook

**Runbook ID**: `RB-007`  
**Target Component**: PostgreSQL Primary/Standby & Async Engine Connection Pool  
**Severity Level**: Critical (P0)  
**Execution Trigger**: PostgreSQL primary node failure or asyncpg connection pool exhaustion  

---

## 1. Objective & Scope

Procedure for managing PostgreSQL database failover and resetting application connection pools.

---

## 2. Recovery Procedure

1. **Promote Multi-AZ Standby Database to Primary**.
2. **Reset Application Connection Pools**:
   - Issue SIGHUP or execute rolling restart of backend API containers to recycle `async_engine` connections:
   ```bash
   aws ecs update-service --cluster carexport-cluster --service carexport-backend-service --force-new-deployment
   ```
3. **Verify Readiness Probe**:
   - Query `/health/ready` until status returns `{"status": "ready", "database": "connected"}`.
