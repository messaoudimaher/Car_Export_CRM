# RB-011: Security Incident & Account Suspension Isolation Runbook

**Runbook ID**: `RB-011`  
**Target Component**: Multi-Tenant Authorization Core & User Account State  
**Severity Level**: Critical Security Emergency (P0)  
**Execution Trigger**: Detected account compromise, suspicious bulk query pattern, or tenant isolation breach attempt  

---

## 1. Objective & Scope

Emergency containment runbook for isolating compromised accounts or revoking tenant access instantly.

---

## 2. Immediate Containment Procedure

1. **Suspend Compromised User Account**:
   ```sql
   UPDATE users SET is_active = FALSE WHERE email = 'compromised@tenant.com';
   ```
2. **Revoke Active Tokens**:
   - Invalidate tenant session cache in Redis:
   ```bash
   redis-cli DEL "session:user:<USER_ID>"
   ```
3. **Audit Trail Inspection**:
   - Query `audit_events` for unauthorized attempts (`SEC-009`):
   ```sql
   SELECT * FROM audit_events WHERE user_id = '<USER_ID>' ORDER BY created_at DESC;
   ```
