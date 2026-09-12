---
name: security
description: >-
  Use this skill when auditing tenant boundaries, checking webhook signature verification, performing IDOR checks, validating input sanitization, or reviewing AI prompt injection defenses.
---

# Security Audit & Risk Verification Skill

## 1. Purpose & Scope
Provide security audit procedures, multi-tenant isolation verification, secret safety checks, HMAC webhook signature checks, and OWASP compliance validation.

## 2. Activation Triggers
Activate during security review stage of feature delivery, when auditing API endpoints, checking authentication context handling, or reviewing AI input safety.

## 3. Inspection Targets
- [`SECURITY.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/SECURITY.md) (10-point feature security checklist)
- [`AGENTS.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/AGENTS.md) (Human Approval Gates for High/Critical risks)

## 4. Constraints
- **Tenant Identity Authority**: Reject any endpoint or query that trusts `tenant_id` supplied in request bodies, query params, or client headers.
- **Zero Accepted High/Critical Risks**: High or Critical security vulnerabilities MUST block feature completion until remediated.
- **Webhook HMAC Signature**: All inbound webhook handlers MUST enforce signature verification before processing body payloads.

## 5. Execution Procedure
1. Execute 10-point Security Checklist from [`SECURITY.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/SECURITY.md).
2. Audit DB queries for `tenant_id` filtering.
3. Check IDOR protection on resource endpoints (`/leads/{id}`, `/quotes/{id}`).
4. Verify PII scrubbing in logs and LLM prompt inputs.

## 6. Expected Outputs
- Security audit report.
- Remediated vulnerability findings or Human Gate escalation if High/Critical risks discovered.
