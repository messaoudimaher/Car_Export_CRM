---
name: frontend
description: >-
  Use this skill when implementing React/TypeScript user interfaces, building the WhatsApp inbox workspace, designing operational density components, or managing frontend state.
---

# Frontend Engineering & UI Design Skill

## 1. Purpose & Scope
Guide the development of React + TypeScript user interfaces optimized for high-density B2B operations, keyboard navigation, fast scanning, predictable layouts, and zero AI-slop design.

## 2. Activation Triggers
Activate when implementing frontend pages, React components, state management hooks, API integration clients, or operational inbox views.

## 3. Inspection Targets
- [`AGENTS.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/AGENTS.md) (Zero AI-slop UI policy)
- [`docs/api-contracts.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/docs/api-contracts.md) (REST API response envelope structures)

## 4. Constraints
- **Zero AI-Slop Design**: Avoid decorative background gradients, glowing borders, useless glassmorphism, or vanity charts. Prioritize data density, keyboard shortcuts, fast filtering, and clear status badges.
- **Strict TypeScript**: `"strict": true` in `tsconfig.json`. No `any` types.
- **Human Control UI**: AI suggestions MUST render with distinct "AI Suggested" tags and explicit "Edit" and "Approve & Send" buttons.

## 5. Execution Procedure
1. Design high-density operational layout (e.g., 3-panel WhatsApp inbox workspace: Thread list | Chat history | Customer & Sourcing sidebar).
2. Implement typed React component with TanStack Query hooks for server state management.
3. Ensure accessible form inputs, clear loading/error states, and keyboard shortcut listeners.

## 6. Expected Outputs
- Fully typed React/TypeScript components.
- Responsive, high-density B2B operational interface.
