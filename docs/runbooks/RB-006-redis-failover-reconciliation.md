# RB-006: Redis Store Failover & Reconciliation Re-enqueue Runbook

**Runbook ID**: `RB-006`  
**Target Component**: Redis Primary/Replica & ARQ Queue  
**Severity Level**: High (P1)  
**Execution Trigger**: Redis container node failover or connection timeout errors  

---

## 1. Objective & Scope

Procedure for handling Redis cache/queue node failovers and recovering state without data loss.

---

## 2. Invariant Guarantee

PostgreSQL is the single source of truth for inbound WhatsApp messages (`BR-008`). Redis contains transient queue jobs and session cache. **Redis downtime NEVER causes data loss**.

---

## 3. Recovery Procedure

1. **Verify Primary Redis Node Failover**.
2. **Flush Corrupted Cache Keyspaces** (`cache:<tenant_id>:*`).
3. **Execute DB Reconciliation**:
   - Re-enqueue pending DB messages into recovered Redis instance.
