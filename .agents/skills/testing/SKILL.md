---
name: testing
description: >-
  Use this skill when writing unit tests, API integration tests, mock provider fixtures, frontend Vitest specs, or verifying test suite coverage.
---

# Testing & Quality Assurance Skill

## 1. Purpose & Scope
Enforce testing standards, fixture setups, provider mocking, API integration testing, and test suite execution across backend (`pytest`) and frontend (`vitest`).

## 2. Activation Triggers
Activate when writing unit tests, integration tests, mock fixtures, cross-tenant security test assertions, or running verification commands.

## 3. Inspection Targets
- [`DEVELOPMENT.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/DEVELOPMENT.md) (Test execution commands & DoD standards)
- [`SECURITY.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/SECURITY.md) (Cross-tenant security test requirements)

## 4. Constraints
- **Cross-Tenant Isolation Test Mandatory**: Every new entity API endpoint MUST include an explicit cross-tenant isolation test verifying that Tenant B receives `404 Not Found` when requesting Tenant A's resources.
- **Provider Mocking**: External services (WhatsApp, OpenAI, S3) MUST be mocked using Port interface test double implementations.
- **Zero Masking of Failures**: Never comment out failing assertions or return empty fallbacks to bypass test suite failures.

## 5. Execution Procedure
1. Create unit test for business service methods (`pytest`).
2. Create API endpoint integration test using `httpx.AsyncClient` and test JWT credentials.
3. Add cross-tenant isolation test assertion.
4. Execute test suite: `pytest src/backend/tests` and `npm run test`.

## 6. Expected Outputs
- Passing test suite with high coverage for new features.
- Verified cross-tenant boundary assertions.
