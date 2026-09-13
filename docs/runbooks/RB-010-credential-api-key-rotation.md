# RB-010: Security Credential & API Key Rotation Runbook

**Runbook ID**: `RB-010`  
**Target Component**: JWT Signing Keys, Database Passwords, Third-Party API Keys  
**Severity Level**: High / Security Maintenance (P1)  
**Execution Trigger**: Scheduled 90-day secret rotation or security compromise event  

---

## 1. Objective & Scope

Procedure for safely rotating encryption keys, database credentials, JWT secret keys, and third-party API keys without service interruption.

---

## 2. Rotation Step-by-Step Procedure

1. **JWT Secret Key Rotation**:
   - Update `JWT_SECRET_KEY` in environment secrets manager. Active tokens remain valid during dual-key transition window.
2. **Database Password Rotation**:
   - Update PostgreSQL role password, update application secret, and reload application tasks.
3. **WhatsApp / OpenAI API Key Rotation**:
   - Generate new API key in vendor portal, update container environment variable, and verify outbound connectivity.
