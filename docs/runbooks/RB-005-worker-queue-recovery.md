# RB-005: Background Worker Queue Recovery & DB Reconciliation Runbook

**Runbook ID**: `RB-005`  
**Target Component**: Redis ARQ Queue & PostgreSQL Reconciliation Worker  
**Severity Level**: High (P1)  
**Execution Trigger**: Redis queue backlog spike or worker container crashes  

---

## 1. Objective & Scope

Procedure for recovering hung Redis ARQ background worker tasks and executing DB reconciliation for messages persisted in PostgreSQL during worker downtime.

---

## 2. Recovery Procedure

1. **Check ARQ Queue Depth Gauge**:
   - Inspect Prometheus metric `arq_queue_depth`.
2. **Execute Reconciliation Script**:
   - Query un-processed messages (`processed_at IS NULL AND created_at < NOW() - INTERVAL '5 minutes'`) and re-enqueue:
   ```bash
   python -m app.workers.reconciliation
   ```
3. **Inspect Dead Letter Queue (DLQ)**:
   - Poison payloads reaching max retries move to DLQ for manual inspection (`SEC-011`).
