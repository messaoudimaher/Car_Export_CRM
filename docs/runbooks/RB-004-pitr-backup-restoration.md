# RB-004: PostgreSQL Backup Restoration (PITR Drill) Runbook

**Runbook ID**: `RB-004`  
**Target Component**: PostgreSQL Database & S3 WAL Archive  
**Severity Level**: Critical / Disaster Recovery (P0)  
**Execution Trigger**: Accidental table drop, database corruption, or quarterly DR drill  

---

## 1. Objective & Scope

Procedure for executing Point-in-Time Recovery (PITR) to restore database state up to a targeted pre-incident timestamp with < 5 minute RPO and < 1 hour RTO targets.

---

## 2. Automated Restore Execution

Execute automated restore drill script:
```bash
./scripts/test_pitr_restore.sh
```

Or execute Python runner:
```bash
python scripts/test_pitr_restore.py
```

---

## 3. Manual PITR Recovery Protocol

1. **Locate Base Backup & WAL Stream in S3**:
   ```bash
   aws s3 ls s3://carexport-backups-prod/wal_archives/
   ```
2. **Provision Target Recovery Database Instance**.
3. **Configure `recovery.signal` & `postgresql.conf`**:
   ```ini
   restore_command = 'aws s3 cp s3://carexport-backups-prod/wal_archives/%f %p'
   recovery_target_time = '2026-09-13 23:00:00+00'
   ```
4. **Start PostgreSQL Instance & Verify Canary Records**.
