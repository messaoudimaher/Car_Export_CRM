# ADR 0016: Operational Density Design System and Inbox Workspace

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM is a specialized B2B CRM designed for European car exporters handling high-volume WhatsApp sourcing requests from buyers in Tunisia. 

Many modern web frameworks and AI tools default to low-density SaaS dashboards (oversized cards, rounded container padding, decorative background gradients, glowing borders, glassmorphism slop, and vanity KPI charts). These patterns harm operational efficiency for professional sales reps who need maximum information density, keyboard navigation, fast filtering, clear status indicators, and unambiguous distinction between customer communication, AI suggestions, and authoritative business data.

---

## 2. Decision Drivers

- **Inbox-First Operational Primary Workspace**: The primary user journey flows from WhatsApp Conversation → Customer → Vehicle Request → Lead → Follow-up → Quote → Order. The Inbox workspace is the core operational screen.
- **Zero AI-Slop Design Policy**: Strict prohibition of decorative gradients, glowing AI borders, glassmorphism slop, oversized headings, and vanity charts.
- **Information Density & Keyboard-First UX**: Maximize visible data per screen height, compact table layouts, tabular monospace numbers, and full keyboard shortcut accessibility (`j`/`k` navigation, `r` reply, `a` approve AI suggestion).
- **Explicit AI Trust Boundaries**: Visual hierarchy MUST make provisional AI understandings/suggestions unmistakably distinct from confirmed business ground truth (`INV-003`, `INV-006`, `ADR 0012`, `ADR 0014`).

---

## 3. Decision Outcome

**Chosen Option**: **3-Pane Operational Inbox Workspace + High-Density Design System Baseline**.

### 1. 3-Pane Operational Workspace Layout:
- **Left Pane (320px fixed)**: Thread List with search bar, status tabs (`All`, `Unassigned`, `Unread`, `Needs Action`), priority badges, E.164 phone number, latest snippet, and relative timestamp.
- **Center Pane (flex 1)**: Active Thread Header (Customer identity, Assignee avatar, Status selector) + Scrollable Chat History (Message bubbles with `wamid` delivery receipts, document thumbnails) + Reply Box with AI suggestion banner.
- **Right Pane (380px fixed/collapsible)**: Customer Profile & Sourcing Sidebar (Customer contact details, active Vehicle Requests, Lead stage pipeline, Quick Quote Generator, Activity timeline).

### 2. High-Density Design System Tokens & Conventions:
- **Color Palette**: Slate/Neutral dark (`#0f172a` dark mode, `#f8fafc` light mode), Emerald green for confirmed business truth, Indigo for AI provisional states, Amber for pending review, Rose for errors/warnings. Zero decorative gradients or glowing borders.
- **Typography & Formatting**: Inter / Roboto typeface; tabular monospace numbers (`font-mono` / `font-variant-numeric: tabular-nums`) for currency amounts (€ and DT) and vehicle VINs.
- **Spacing Scale**: 4px base scale (`p-1`, `p-2`, `p-3`, `p-4`), compact table padding (`py-1.5 px-3`), letter-spacing tight.

### 3. Explicit Visual Hierarchy for AI HITL Boundary:
- `CUSTOMER MESSAGE`: Light Grey bubble, left-aligned, tagged `<untrusted_user_message>`.
- `AI UNDERSTANDING`: Indigo structured banner with badge *"AI Detected — Provisional"* + `[Edit]` `[Confirm]` buttons (`INV-003`).
- `AI SUGGESTION`: Amber/Blue container with badge *"Suggested Reply — Not Sent"* + `[Edit Prompt]` `[Approve & Send]` buttons (`ADR 0012`).
- `HUMAN RESPONSE`: Green/Blue bubble, right-aligned, representing confirmed sales agent dispatch.
- `AUTHORITATIVE BUSINESS DATA`: Solid dark table card with badge *"Confirmed Ground Truth"*.

---

## 4. Consequences

### Positive:
- Provides high information density tailored for professional B2B car export operations.
- Eliminates cognitive load by visually isolating provisional AI text from confirmed database truth.
- Ensures fast keyboard-driven workflow for sales agents processing 50+ threads daily.

### Negative / Mitigation:
- Requires strict component governance to prevent accidental inclusion of low-density design patterns or unescaped HTML elements (enforced via frontend architecture standards and automated integration tests).
