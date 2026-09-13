# RB-008: Meta WhatsApp Webhook Ingestion Outage Recovery Runbook

**Runbook ID**: `RB-008`  
**Target Component**: Meta WhatsApp BSP Router & Webhook Signature Middleware  
**Severity Level**: High (P1)  
**Execution Trigger**: Meta Cloud API outage or webhook signature verification failure spikes  

---

## 1. Objective & Scope

Procedure for recovering WhatsApp webhook message ingestion following Meta API outages or secret rotation.

---

## 2. Ingestion Principles

- **Pre-ACK Persistence**: Inbound webhooks persist messages to PostgreSQL BEFORE returning HTTP 200 ACK (`BR-008`).
- **Atomic Deduplication**: Duplicate `wamid` payloads are ignored gracefully via unique constraints.

---

## 3. Outage Recovery Procedure

1. **Verify Meta API Status**.
2. **Rotate Webhook Verify Token / App Secret** if signature validation fails (`RB-010`).
3. **Re-trigger Backlogged Meta Webhook Events**.
