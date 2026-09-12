---
name: code-review
description: >-
  Use this skill when auditing code changes, reviewing git diffs against the Definition of Done, checking type safety, evaluating modularity, or verifying test coverage.
---

# Code Review & DoD Verification Skill

## 1. Purpose & Scope
Provide a structured audit checklist for evaluating git diffs, verifying technical quality, ensuring strict type safety, and confirming compliance with the Definition of Done.

## 2. Activation Triggers
Activate during the code review stage of feature delivery, before merging PRs, or when auditing pull request diffs.

## 3. Inspection Targets
- [`DEVELOPMENT.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/DEVELOPMENT.md) (Definition of Done & typing standards)
- [`AGENTS.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/AGENTS.md) (Non-negotiable engineering principles)

## 4. Constraints
- **DoD Compliance Required**: Zero type errors (`mypy`, `tsc`), zero linter warnings (`ruff`), zero test failures (`pytest`, `vitest`).
- **No Unrelated Collateral Refactoring**: Diffs must remain strictly focused on the requested feature.
- **Zero Dead Code**: Remove commented-out code blocks, temporary debug print statements, or unused imports before approval.

## 5. Execution Procedure
1. Execute linter/formatter check: `ruff check .`
2. Run backend type checker: `mypy src/backend`
3. Run frontend type checker: `npm run type-check`
4. Run test suite: `pytest` and `vitest`
5. Audit diff against DoD checklist in [`DEVELOPMENT.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/DEVELOPMENT.md).

## 6. Expected Outputs
- Detailed code review finding report categorized by severity (`BLOCKER`, `MAJOR`, `MINOR`).
- Explicit Approval or Actionable Remediation list.
