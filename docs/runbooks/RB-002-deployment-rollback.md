# RB-002: Deployment Rollback Procedure Runbook

**Runbook ID**: `RB-002`  
**Target Component**: ECS Compute Nodes & Container Task Definitions  
**Severity Level**: Urgent / High (P1)  
**Execution Trigger**: Unhandled error rate spike (> 2% HTTP 500s) or failing readiness probes post-deployment  

---

## 1. Objective & Scope

Emergency rollback procedure for reverting active compute containers back to the previous known-good immutable commit SHA (`PREVIOUS_SHA`) without downtime.

---

## 2. Emergency Rollback Step-by-Step Procedure

1. **Identify Previous Deployable Commit SHA**:
   ```bash
   PREVIOUS_SHA=$(git rev-parse HEAD~1)
   echo "Rolling back to immutable tag: ${PREVIOUS_SHA}"
   ```
2. **Revert ECS Service Task Definition**:
   ```bash
   aws ecs update-service --cluster carexport-cluster --service carexport-backend-service --task-definition carexport-backend:${PREVIOUS_SHA} --force-new-deployment
   ```
3. **Revert Frontend Static Asset Route**:
   - Point CDN / Nginx router to previous static release directory:
   ```bash
   aws s3 sync s3://carexport-frontend-releases/${PREVIOUS_SHA}/ s3://carexport-frontend-prod/
   ```
4. **Database Rollback Note**:
   - Schema modifications follow the `Expand-Migrate-Contract` pattern (`ADR 0017`). Database schemas are backward-compatible with `${PREVIOUS_SHA}` code; DO NOT execute database downgrades during emergency compute rollbacks.

---

## 3. Post-Rollback Verification

- Confirm HTTP 500 error rates drop to 0%.
- Verify `/health/ready` probe status returns `HTTP 200 OK`.
