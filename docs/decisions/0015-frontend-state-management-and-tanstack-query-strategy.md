# ADR 0015: Frontend State Management and TanStack Query Strategy

- **Status**: Approved
- **Date**: 2026-09-11
- **Deciders**: Lead Engineering Agent, Project Owner

---

## 1. Context & Problem Statement

Car-Export-CRM is a high-density B2B operational CRM where sales reps handle real-time WhatsApp incoming messages, AI vehicle request understandings, lead progression, and quote generation concurrently. 

A key challenge in complex React applications is state management bloat—mixing server-derived data (customers, conversations, quotes) with transient client UI state (active modal, active tab, filter selections). Global client state stores (e.g. Redux) often introduce unnecessary boilerplate, stale cache bugs, and synchronization friction with REST APIs. We need a clear, performance-optimized, and maintainable state management architecture.

---

## 2. Decision Drivers

- **Clear Separation of Concerns**: Strict separation between Server State (persisted backend data) and Client/UI State (transient view state).
- **Fast, Responsive UX**: Instant UI feedback via optimistic updates for common actions (message dispatch, lead status change, thread assignment).
- **Cache Efficiency & Consistency**: Standardized query key factories and automatic cache invalidation on mutations.
- **Contract Alignment**: Direct 1:1 alignment with FastAPI backend REST endpoints and RFC 7807 problem details.
- **Operational Simplicity**: Avoid complex global state libraries for data that belongs in the API query cache or URL.

---

## 3. Decision Outcome

**Chosen Option**: **TanStack Query (React Query) v5 for Server State + URL Search Parameters for View Filter State + React Context / Local State for Transient UI Elements**.

### Architectural Breakdown:

1. **Server State Management (TanStack Query v5)**:
   - All server data fetching, caching, synchronization, background refetching, and mutation states are managed exclusively by TanStack Query.
   - Structured Query Key Factories ensure strict type-safe cache management:
     ```typescript
     export const inboxKeys = {
       all: ['inbox'] as const,
       threads: (filters: ThreadFilterParams) => [...inboxKeys.all, 'threads', filters] as const,
       thread: (id: string) => [...inboxKeys.all, 'thread', id] as const,
       messages: (threadId: string) => [...inboxKeys.all, 'messages', threadId] as const,
     };
     ```
   - Stale Time Policy: Configured per resource type (e.g. Inbox threads `staleTime: 5000ms`, Customer static records `staleTime: 60000ms`, Vehicle catalog `staleTime: 300000ms`).

2. **Client / View State via URL Search Parameters**:
   - Filter states, pagination indices, active tabs, and search queries are stored directly in the URL query string (`?status=ACTIVE&search=BMW&page=1`).
   - Enables deep-linking, browser history navigation (`Back`/`Forward`), and shareable operational views across sales team members.

3. **Transient UI State (React Context / Local State)**:
   - Modal visibility, drawer toggles, active thread selection, and uncommitted draft reply text reside in local React component state (`useState`) or lightweight feature React Context. No global Redux store is introduced.

4. **Optimistic UI Updates Strategy**:
   - High-frequency user actions (sending a chat reply, changing thread assignee, toggling lead stage) apply optimistic cache updates immediately before API response confirmation.
   - On mutation error, TanStack Query automatically rolls back cache state to snapshot state and displays an RFC 7807 error toast.

---

## 4. Consequences

### Positive:
- Eliminates 80%+ of state boilerplate compared to traditional Redux/Zustand global stores.
- Guarantee of fresh server data with automated stale-while-revalidate caching.
- Native deep-linking and browser navigation support out of the box.
- Seamless optimistic UI response times for operational sales agents (< 50ms user-perceived latency).

### Negative / Mitigation:
- Requires strict adherence to Query Key Factories to prevent cache key collisions or invalidation oversights (enforced via component code review and integration tests).
