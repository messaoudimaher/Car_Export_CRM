# RB-009: LLM Provider Outage & Circuit Breaker Reset Runbook

**Runbook ID**: `RB-009`  
**Target Component**: LLM Provider Port Abstraction & Circuit Breaker  
**Severity Level**: Medium (P2)  
**Execution Trigger**: OpenAI / Anthropic API latency spike or 5xx error rate breach  

---

## 1. Objective & Scope

Procedure for managing external LLM API outages and resetting circuit breaker fallbacks without impacting core CRM operations.

---

## 2. Fundamental Invariant

**Third-Party Failure Isolation Invariant**: External LLM outages MUST NEVER degrade core CRM application health, login, customer viewing, or manual message replies.

---

## 3. Circuit Breaker Procedure

1. **Automatic Circuit Tripping**: When LLM error rate exceeds 50% over 2 minutes, circuit breaker trips to `OPEN` state.
2. **Fallback to Demo/Manual Mode**: Incoming messages transition automatically to human sales rep inbox timeline (`HITL`).
3. **Manual Reset**:
   ```bash
   python -m app.core.circuit_breaker --reset --provider llm
   ```
