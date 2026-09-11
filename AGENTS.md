# AGENTS.md - Engineering Operating System & Agent Protocol

Welcome to the **Car-Export-CRM** project repository. This document defines the engineering operating system, collaboration protocols, instruction hierarchy, role definitions, and non-negotiable guidelines for all AI agents and human engineers working on this codebase.

---

## 1. Hierarchy of Authority

When resolving conflicting directives, all agents and contributors MUST adhere to the following 7-tier strict precedence hierarchy (1 = Highest Authority):

1. **User Request**: Explicit directive supplied by the user in the active turn.
2. **Project Engineering Rules (`AGENTS.md`)**: Non-negotiable repository governance and engineering contract.
3. **Product Requirements (`PRODUCT.md`)**: Business domain boundaries, target market rules, and MVP scope limits.
4. **System Architecture (`ARCHITECTURE.md`)**: Modular Monolith pattern, layer boundaries, and provider abstractions.
5. **Security Policy (`SECURITY.md`)**: Multi-tenant isolation, authorization, and vulnerability controls.
6. **Relevant Workspace Skill (`.agents/skills/`)**: Specialized workflow instructions and runbooks.
7. **Feature / Task Instructions**: Local design notes or inline task specifications.

> **Rule**: No skill or task instruction may silently override project-wide security, architecture, or engineering rules.

---

## 2. Core Role Matrix & Responsibility Boundaries

- **SKILLS (`.agents/skills/`)**: Reusable engineering expertise, workflow standards, and procedural runbooks. Skills are *knowledge assets*, not independent execution threads.
- **AGENTS (`.agents/agents/`)**: Specialized worker role definitions that may execute focused, independent sub-tasks delegated by the Main Agent.
- **MAIN AGENT (Lead Engineering Agent)**: The primary coordinator, product/technical translator, architecture gatekeeper, and quality router.

### Main Agent Routing Protocol:
The Main Agent MUST automatically determine and apply the necessary skills and subagent workflows based on user intent. The user should NEVER be required to specify skills manually.

| User Intent Example | Required Skills Activated | Subagent Orchestration |
| :--- | :--- | :--- |
| *"Implement WhatsApp message ingestion"* | `product` → `architecture` → `backend` → `ai-engineering` → `security` → `testing` → `code-review` | `architect` → `backend-engineer` → `ai-engineer` → `qa-engineer` → `reviewer` |
| *"Add quote PDF generation"* | `product` → `backend` → `security` → `testing` → `code-review` | `backend-engineer` → `qa-engineer` → `reviewer` |
| *"Refactor lead inbox UI table"* | `frontend` → `code-review` | `frontend-engineer` → `reviewer` |

---

## 3. Human Approval Gates (Non-Negotiable)

The Main Agent may autonomously execute standard implementation tasks.

**The Main Agent MUST pause and request explicit Human Approval before executing decisions that involve:**

1. **Architecture Changes**: Deviating from the Modular Monolith pattern or altering core module contracts.
2. **Microservices / Infrastructure**: Introducing microservices, service meshes, event buses, or Kubernetes.
3. **Database Strategy**: Switching database engine, altering multi-tenant storage model, or changing migration frameworks.
4. **Third-Party Providers**: Adding or swapping core infrastructure providers (WhatsApp BSP, LLM provider, Payment gateway, Storage).
5. **Auth & Identity**: Changing authentication mechanisms, token structure, or session storage.
6. **Tenant Isolation Strategy**: Modifying how tenant context is resolved, propagated, or enforced.
7. **Consequential AI Actions**: Granting AI authority to execute financial, contractual, or inventory mutations directly.
8. **MVP Scope Expansion**: Adding features not explicitly part of the defined MVP journey.
9. **High/Critical Security Risks**: Accepting or bypassing identified high or critical security vulnerabilities.
10. **Destructive Operations**: Dropping database tables, truncating data, or deleting major source paths.

---

## 4. Safe Parallel Execution & Synchronization Rules

Parallel subagent execution is permitted **ONLY when sub-tasks are genuinely independent**.

### Safe Parallelization Scenarios:
- **Decoupled Layer Implementation**: Backend API endpoints and Frontend UI components may be implemented concurrently *ONLY AFTER* API contracts (`docs/api-contracts.md`) and domain schemas (`docs/domain-model.md`) are finalized and committed.
- **Independent Test Creation**: Writing unit tests for Module A while writing integration tests for Module B.

### Forbidden Parallelization (Must be Sequenced):
- Multiple agents editing the same file or module simultaneously.
- Multiple agents creating or modifying Alembic database migrations concurrently.
- Multiple agents altering the same API contract or domain schema simultaneously.

> **Reconciliation Protocol**: When parallel execution finishes, the Main Agent MUST inspect, merge, and verify the combined diff before proceeding to testing or code review.

---

## 5. Non-Negotiable Engineering Principles

1. **Domain Isolation from External Provider SDKs**:
   Business logic must NEVER import provider SDKs directly (e.g., Meta WhatsApp API, OpenAI SDK, AWS S3 SDK). All external capabilities MUST pass through generic interface adapters (`WhatsAppProvider`, `LLMProvider`, `ObjectStorageProvider`).
2. **Tenant Identity Context**:
   Tenant context MUST always be derived from authenticated user credentials (JWT / session token). NEVER trust a `tenant_id` supplied in request bodies, query params, or client headers.
3. **AI Non-Authoritative Boundary**:
   AI outputs are classified as **proposals/suggestions**. AI cannot directly mutate prices, inventory availability, shipping dates, or legal FCR export documents without human validation.
4. **Zero AI Slop UI**:
   The B2B interface prioritizes information density, keyboard navigation, fast filtering, and clear status visibility over decorative animations, glassmorphism, or unused charts.

---

## 6. Shared Project Memory & Documentation Discipline

The repository itself is the single source of truth. Agents must not rely on hidden conversational memory across turns.

- **Business Domain**: [`PRODUCT.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/PRODUCT.md) & [`docs/domain-model.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/domain-model.md)
- **Technical Architecture**: [`ARCHITECTURE.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/ARCHITECTURE.md) & [`docs/decisions/`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/decisions/)
- **API Contracts**: [`docs/api-contracts.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/api-contracts.md)
- **AI Architecture**: [`docs/ai-architecture.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/ai-architecture.md)
- **Security Policy**: [`SECURITY.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/SECURITY.md)
- **Engineering Standards**: [`DEVELOPMENT.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/DEVELOPMENT.md)

---

## 7. Mandatory Task Execution Git Commit & Push Protocol

Upon completion of EVERY engineering task, after all verification checks pass cleanly:
1. Stage and commit implementation source code, project architectural documentation (`AGENTS.md`, `PRODUCT.md`, `ARCHITECTURE.md`, `SECURITY.md`, `DEVELOPMENT.md`, `docs/**/*.md`), and configuration files into version control.
2. Ensure temporary scratch/task execution artifacts remain untracked.
3. Push committed changes to remote repository: `git@github.com:messaoudimaher/Car_Export_CRM.git`.

---

## 8. Wave Completion Reporting Protocol

Upon completion of EVERY implementation wave (or workstream group within a wave), the Lead Agent MUST generate a **Wave Completion Summary Report** covering:
1. **Tasks Executed**: Summary of all completed tasks in the wave with test verification status and remote git commit hashes.
2. **Gaps / Missed Items**: Explicit list of deferred items, open risks, or architectural gaps (if any).
3. **Environment Variables Reference**: Complete list of environment variables introduced, updated, or required to be configured across development, staging, and production environments.


