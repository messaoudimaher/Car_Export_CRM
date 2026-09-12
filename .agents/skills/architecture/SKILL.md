---
name: architecture
description: >-
  Use this skill when designing technical implementations, evaluating module boundaries, creating provider port interfaces (WhatsApp, LLM, Storage), drafting ADRs, or enforcing the Modular Monolith pattern.
---

# Architecture & Module Boundary Skill

## 1. Purpose & Scope
Enforce the Modular Monolith architecture, dependency inversion (Port & Adapter pattern), clean module layer separation, and ADR documentation discipline.

## 2. Activation Triggers
Activate when designing new technical capabilities, establishing module boundaries, creating provider ports, or evaluating system refactoring.

## 3. Inspection Targets
- [`ARCHITECTURE.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/ARCHITECTURE.md) (Modular Monolith rules & directory layout)
- [`docs/decisions/`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/decisions/) (Architecture Decision Records)
- [`AGENTS.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/AGENTS.md) (Human Approval Gates for architecture)

## 4. Constraints
- **Modular Monolith Strictness**: Reject premature microservices, separate service repositories, or distributed event buses.
- **Port & Adapter Inversion**: Application modules MUST NEVER import third-party SDKs directly (`openai`, `facebook-sdk`, `boto3`). All external capabilities must pass through Port interfaces in `app/ports/`.
- **Module Independence**: Core modules (`messaging`, `customers`, `sourcing`, `quotes`, `ai_engine`) must interact via service layer interfaces, never raw cross-module database SQL joins.

## 5. Execution Procedure
1. Review proposed module placement against `ARCHITECTURE.md`.
2. Define abstract Port interface in `src/backend/app/ports/` if introducing an external service dependency.
3. Place concrete SDK implementations in `src/backend/app/adapters/`.
4. Draft ADR in `docs/decisions/000X-title.md` for major architectural decisions.

## 6. Expected Outputs
- Validated architectural design adhering to Port & Adapter pattern.
- Drafted or updated ADR in `docs/decisions/`.
