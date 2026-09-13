# RB-001: Application Deployment & Zero-Downtime Release Runbook

**Runbook ID**: `RB-001`  
**Target Component**: CI/CD Pipeline & ECS Compute Nodes  
**Severity Level**: Standard Operation (P3)  
**Execution Trigger**: Code merge to `main` branch or release tag creation  

---

## 1. Objective & Scope

Standard operating procedure for executing zero-downtime rolling updates of backend API compute nodes, ARQ worker containers, and frontend static assets.

---

## 2. Pre-Deployment Verification Checklist

- [ ] All 6 CI quality gate jobs in `.github/workflows/ci.yml` must show **PASS**.
- [ ] Database schema migrations tested locally (`alembic upgrade head`).
- [ ] Container images built and tagged with immutable `${{ github.sha }}`.
- [ ] Trivy vulnerability scan reports zero `CRITICAL` vulnerabilities (`exit-code: 1`).

---

## 3. Deployment Step-by-Step Procedure

1. **Trigger CI/CD Pipeline**:
   - Merge approved PR into `main` branch.
2. **Execute Database Migrations**:
   - Migration task executes once in isolation prior to container swap:
   ```bash
   aws ecs run-task --cluster carexport-cluster --task-definition carexport-migration:latest
   ```
3. **Trigger Rolling Container Update**:
   - Update backend service with new image tag:
   ```bash
   aws ecs update-service --cluster carexport-cluster --service carexport-backend-service --task-definition carexport-backend:${COMMIT_SHA} --minimum-healthy-percent 100 --maximum-percent 200
   ```
4. **Monitor Health Probes**:
   - Poll `/health/ready` endpoint until 100% of new container instances report `HTTP 200 OK`.

---

## 4. Post-Deployment Verification

- Execute API smoke tests on `/api/v1/health` and `/metrics`.
- Verify zero unexpected error spikes in structured logs (`structlog`).
