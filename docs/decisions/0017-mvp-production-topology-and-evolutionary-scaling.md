# ADR 0017: MVP Production Topology and Evolutionary Infrastructure Scaling

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM is a multi-tenant B2B SaaS platform for European car exporters managing WhatsApp sourcing workflows. During early infrastructure planning, engineering teams often face the temptation to introduce complex Kubernetes (K8s) clusters, service meshes (e.g. Istio), distributed tracing setups, or premature microservice topologies before reaching product-market fit or measurable scaling bottlenecks.

We must define an authoritative minimum viable production topology that is operationally simple, highly cost-effective, fault-tolerant, secure, and fully aligned with our Modular Monolith baseline (`ADR 0001`) and Evolutionary Service Extraction criteria (`ADR 0004`).

---

## 2. Decision Drivers

- **Operational Simplicity**: Low operational burden for small engineering teams; easy to deploy, observe, and troubleshoot without dedicated K8s operators.
- **Durable Business Data Invariant**: PostgreSQL is the ONLY authoritative system of record for inbound WhatsApp events and business ground truth. Redis serves strictly as a task queue and ephemeral cache.
- **Cost Consciousness**: Avoid paying $500+/month for unused Kubernetes control planes and idle microservice infrastructure during early MVP deployment.
- **Fault Tolerance & Webhook Resiliency**: Inbound WhatsApp webhooks persist to PostgreSQL first, ensuring zero message loss even during transient Redis worker queue outages.
- **Anti-Premature-Kubernetes Invariant**: Kubernetes MUST NOT be the MVP default. Managed services + stateless compute nodes are preferred.
- **Security & Multi-Tenancy**: Private subnet isolation for database and Redis; TLS 1.3 preferred (TLS 1.2 fallback where required); zero hardcoded secrets; worker context validation (`SEC-011`).

---

## 3. Decision Outcome

**Chosen Option**: **Stateless App Nodes + PostgreSQL-First Inbound Event Persistence + Asynchronous Workers + Managed PostgreSQL (with pgvector) + Managed Redis + Managed S3 Private Object Storage**.

### 1. Inbound Webhook Durability Sequence:
```text
WhatsApp Cloud API
       ↓
TLS Edge (TLS 1.3 / 1.2 fallback)
       ↓
FastAPI Webhook Endpoint
       ↓
HMAC-SHA256 Verification (BR-007)
       ↓
Payload Validation
       ↓
Atomic wamid Deduplication in PostgreSQL (BR-008)
       ↓
Persist Inbound Message Record in PostgreSQL (System of Record)
       ↓
Enqueue Processing Job in Redis ARQ Queue
       ↓
HTTP 200 OK Response (< 200 ms Internal Target)
```
*Redis Failure Recovery*: If Redis is temporarily unavailable after PostgreSQL persistence, the webhook STILL returns HTTP 200 OK because the message is safely stored in PostgreSQL. A lightweight DB reconciliation job detects un-enqueued/un-processed records (`processed_at IS NULL AND created_at < NOW() - 5m`) and enqueues them automatically once Redis restores connectivity.

### 2. Baseline Production Topology:

```text
                         Internet / WhatsApp Meta API
                                      │
                                      ▼
                              ┌───────────────┐
                              │ DNS / TLS Edge│
                              │ Load Balancer │
                              └───────┬───────┘
                                      │
                 ┌────────────────────┴────────────────────┐
                 │                                         │
          ┌──────▼──────┐                           ┌──────▼──────┐
          │ FastAPI App │                           │ FastAPI App │
          │ Instance 1  │                           │ Instance 2  │
          │ (Zone A)    │                           │ (Zone B)    │
          └──────┬──────┘                           └──────┬──────┘
                 │                                         │
                 └────────────────────┬────────────────────┘
                                      │
                             ┌────────▼────────┐
                             │ Durable Queue / │
                             │ Redis (SEC-005) │
                             └────────┬────────┘
                                      │
                 ┌────────────────────┴────────────────────┐
                 │                                         │
          ┌──────▼──────┐                           ┌──────▼──────┐
          │ ARQ Worker  │                           │ ARQ Worker  │
          │ Instance 1  │                           │ Instance 2  │
          │ (Zone A)    │                           │ (Zone B)    │
          └──────┬──────┘                           └──────┬──────┘
                 │                                         │
                 └────────────────────┬────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
   ┌──────▼──────┐             ┌──────▼──────┐             ┌─────▼─────┐
   │ PostgreSQL  │             │    Redis    │             │ S3 Object │
   │ + pgvector  │             │ Cache/Queue │             │  Storage  │
   │ (Private DB)│             │ (Private)   │             │ (Private) │
   └─────────────┘             └─────────────┘             └───────────┘

External Provider Integrations (Outbound Egress Guard):
WhatsApp Cloud API ───────────► /api/v1/webhooks/whatsapp
LLM Provider API   ◄──────────► AI Provider Adapter Port (Server-side)
```

### 3. Infrastructure Component Selections & Failure Domains:
- **API Compute & Multi-Instance HA**: FastAPI application instances and ARQ workers MUST be distributed across **independent failure domains / availability zones** (e.g. Zone A and Zone B) to provide true hardware redundancy.
- **Expand → Migrate → Contract Database Schema Strategy**: All schema changes follow a 5-step zero-downtime evolution:
  1. *Expand*: Apply backward-compatible DB schema additions (new nullable columns, new tables).
  2. *Deploy*: Deploy new application version compatible with both old and new schema.
  3. *Migrate*: Execute data backfill / transformation jobs asynchronously.
  4. *Switch*: Switch application logic to consume new schema elements.
  5. *Contract*: Remove obsolete DB columns/tables in a subsequent release.
  - DDL alterations are executed strictly by the dedicated `car_export_migrator` user role; normal runtime identity (`car_export_app`) cannot execute DDL.

---

## 4. Anti-Premature-Kubernetes Policy & Evolutionary Triggers

Kubernetes MUST NOT be introduced for the MVP. The platform evolves through 3 explicit infrastructure phases:

```
[ Phase 1: MVP Baseline ]
Modular Monolith + Stateless Container Nodes + ARQ Workers + Managed DB / Redis / S3
(Supports 1 - 50 Tenants / ~100k messages/mo / ~$120/mo base compute estimate + variable usage)
        ↓
[ Phase 2: Growth Scaling ]
Horizontal FastAPI scaling + Worker concurrency pools + PostgreSQL Read Replicas + Redis Cluster
(Supports 50 - 500 Tenants / ~2M messages/mo)
        ↓
[ Phase 3: Enterprise / Selective Service Extraction (Only if ADR 0004 criteria met) ]
Extract specialized sub-services into containerized microservices managed via AWS ECS or Kubernetes (EKS)
(Supports 500+ Tenants)
```

### Measurable Triggers for Kubernetes / Microservices Introduction:
1. **Scaling Asymmetry**: A module requires > 10x compute/memory scaling compared to core API servers (`ADR 0004`).
2. **Multi-Team Velocity**: Separate engineering teams require independent release cycles and deployment pipelines (`ADR 0004`).
3. **Hard Workload Isolation / Compliance**: Customer enterprise contract explicitly mandates dedicated single-tenant infrastructure or isolated Kubernetes pod deployments.

---

## 5. Consequences

### Positive:
- Zero Kubernetes control plane overhead or complex YAML manifest maintenance for MVP.
- Ultra-low operational complexity and deployment cost (~$120/month initial cloud infra estimate).
- Fast, reproducible CI/CD deployments (< 5 minutes).
- Direct alignment with `ADR 0001`, `ADR 0004`, and `SEC-001` through `SEC-011`.

### Negative / Mitigation:
- Requires manual compute node scaling triggers if unexpected 100x traffic spike occurs (mitigated by automated Cloud Watch / Grafana alerts set at 70% CPU/Memory threshold).
