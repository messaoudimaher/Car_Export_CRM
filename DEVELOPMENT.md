# DEVELOPMENT.md - Engineering Standards & Development Guide

## 1. Code Quality & Technical Standards

To maintain high architectural cohesion and prevent long-term technical debt, all code contributed to **Car-Export-CRM** must strictly adhere to these guidelines.

---

## 2. Strong Typing & Tooling Enforcement

### Backend (Python):
- **Python Version**: 3.11+ (Managed via `uv` from `pyproject.toml`)
- **Dependency Management**: `uv` package manager (`pyproject.toml` declarative dependencies)
- **Type Annotations**: Mandatory explicit type hints on all function parameters, returns, and class attributes.
- **Type Checker**: `uv run mypy .` in strict mode (`--strict`).
- **Linter & Formatter**: `uv run ruff check .` and `uv run ruff format .`
- **Data Models**: Pydantic v2 schemas for all API inputs, responses, and internal DTOs.

### Frontend (TypeScript / React):
- **TypeScript Version**: 5.0+
- **Strict Mode**: Enabled in `tsconfig.json` (`"strict": true`, `"noImplicitAny": true`).
- **Linter**: `eslint` with TypeScript and React Hooks rules.
- **Formatter**: `prettier`.

---

## 3. Definition of Done (DoD)

Before any feature, refactor, or bugfix is declared complete, the following checklist MUST be fulfilled:

1. **Implementation**: Code fulfills all business requirements specified in `PRODUCT.md` and `docs/domain-model.md`.
2. **Type Verification**:
   - Backend: `uv run ruff check .` and `uv run mypy .` execute with zero errors.
   - Frontend: `npm run type-check` (tsc) executes with zero errors.
3. **Automated Tests**:
   - Unit and integration tests cover new business logic and edge cases.
   - All tests pass cleanly (`uv run pytest`, `vitest`).
4. **Security Validation**:
   - Tenant isolation verified on all new endpoints/queries.
   - Input schemas strictly validated.
   - OWASP principles respected (`SECURITY.md`).
5. **Documentation**:
   - `docs/api-contracts.md` updated if endpoints change.
   - `docs/domain-model.md` updated if domain schemas change.
   - ADR created in `docs/decisions/` if architectural changes occurred.
6. **Clean Diff**: Zero commented-out dead code, temporary debug print statements, or unformatted files.
7. **Git Commit & Remote Push**: Task implementation code is committed and pushed to `git@github.com:messaoudimaher/Car_Export_CRM.git`. `.md` files MUST NOT be pushed to the remote repository.
8. **Wave Completion Report**: Generate a Wave Completion Summary Report summarizing tasks executed, gaps/missed items, and environment variable configuration requirements upon completing an implementation wave.

---

## 4. Structured Logging & Observability

All log statements MUST use structured JSON logging format. 

Every request/task log MUST include standard correlation context:
- `trace_id` / `correlation_id`
- `tenant_id` (if authenticated)
- `user_id` (if authenticated)
- `module`
- `action`

```python
# Example Structured Log
logger.info(
    "processed_whatsapp_message",
    extra={
        "correlation_id": context.correlation_id,
        "tenant_id": context.tenant_id,
        "phone": message.sender_phone,
        "intent": extracted.intent,
    }
)
```

---

## 5. Development Workspace Setup (Target Blueprint)

```bash
# Docker Environment Setup (When running local development stack)
docker compose up -d postgres redis

# Backend Setup (with uv)
cd src/backend
uv venv
uv pip install -e .[dev]
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# Running Backend Verification Suite
uv run ruff check .
uv run mypy .
uv run pytest

# Frontend Setup
cd src/frontend
npm install
npm run dev
```
