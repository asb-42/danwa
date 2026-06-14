# Phase 5 — Workflow-Observability UX Exposure

**Status:** Plan (not yet started)
**Parent plan:** [`workflow-observability.md`](workflow-observability.md) — backend features already shipped in `2a47340`
**Trigger report:** [`2026-06-14_workflow-observability-ux-gap.md`](../reports/2026-06-14_workflow-observability-ux-gap.md)
**Quick wins (already shipped in `00ad6bd`):**
- QW-1: `onGateDecision` SSE handler in `MvpDebateView` → `feedbackStore.logActivity('gate', …)`
- QW-2: Reordered `ExecutionPanel` so gate cards appear above the long node-output log
- QW-3: Auto-`canvasStore.setMode('workflow')` when the execution panel opens; restore to `'blueprint'` on close

This plan covers the **remaining UX exposure** work: turn the already-functional backend
phase-snapshot API into something the user can actually see, in the right places.

---

## Problem Statement

The backend exposes two new APIs (committed in `2a47340`) that the frontend does not consume:

- `GET /api/workflow_exec/{session_id}/phase-snapshots` → list of per-phase state checkpoints
- `GET /api/workflow_exec/{session_id}/phase-snapshots/{node_id}` → full state for one phase

Concretely:

- **`G1 — Phase-snapshot API has no consumer.`** No frontend code calls the endpoints.
  Backend already persists snapshots via `StateSnapshotStore.save(...)` from
  `backend/workflow/nodes/moderator_nodes.py:gate_node_factory()` for every gate phase
  and from the audit decorator for `node.started` events, so a session accumulates
  real history — but the UI never surfaces it.
- **`G2 — ExecutionPanel is only mounted in `BlueprintCanvasView`.`** The other two
  workflow entry points (InputComposer, the MvpDebate result page) have no panel at
  all. So a user who runs a workflow from anywhere other than the canvas sees a
  black box.
- **`G5 — State view is current-state only.`** `get_session_state()` is fetched and
  rendered as a JSON dump, but the *history* (snapshots at each phase boundary) is
  invisible.

`G3` (canvas mode) and `G4` (gate cards scrolled off) are resolved by `00ad6bd` and
are out of scope here.

---

## Goals

1. A user opening a running or completed workflow from **any** entry point can see
   what happened: which gates fired, what each phase decided, what state was at that
   point.
2. The phase-snapshot history is browsable (not just a single current-state JSON blob).
3. No new backend code is required. The plan is **frontend-only**.

### Non-Goals

- New SSE event types
- Backend changes (`StateSnapshotStore`, `audit_logger`, `workflow_exec.py` all stay as-is)
- Editing the canvas graph from the panel
- Persisting view preferences in the database

---

## Architecture Decisions

### A1 — Reuse the existing tab-strip UX pattern

The blueprint editor's right sidebar (`Inspector.svelte`, `blueprint/Palette.svelte`,
`blueprint/store.svelte.js`) already uses a `[role="tablist"]` / `[role="tab"]` /
`aria-expanded` pattern. The new `PhasesTab` slots into `ExecutionPanel` using the
same primitive, so we don't introduce a second tab convention.

### A2 — `phaseSnapshotsStore` is a per-session module-level cache, not a class singleton

Mirrors the `BlueprintCanvasStore` pattern from
`frontend/src/lib/blueprint/store.svelte.js` but:

- One module-level instance (not class) with `$state` for list + map
- `load(sessionId)` triggers the HTTP fetch and populates both
- `invalidate(sessionId)` resets the entry so the next `load` re-fetches
- A single in-flight promise per session avoids duplicate GETs (e.g. when both
  `ExecutionPanel` and `PhaseSnapshotsWidget` mount for the same session)

Rune-store shape:

```js
// frontend/src/lib/stores/phaseSnapshotsStore.svelte.js
import { getPhaseSnapshots, getPhaseSnapshotDetail } from '$lib/api/workflowExec.js';

const bySession = $state({});           // sessionId → { list, detail: { [nodeId]: snapshot }, loading, error }
const inflight = new Map();              // sessionId → Promise<void>

export const phaseSnapshots = {
  get list() { return _list(); },        // derived-by-session
  get detail() { return _detail(); },    // derived-by-session
  load(sessionId) { … },
  invalidate(sessionId) { … },
};
```

The store is **read-only outside** — components call `load()` to populate, and the
UI reacts to the `$state` updates.

### A3 — `PhasesTab` renders the timeline as a flat list, not a graph

The user wants "what happened, in order". A vertical timeline (gate nodes on the
left, decision summary + state hash on the right) maps directly to the audit-log
shape they already see in the panel. Re-rendering the canvas graph is **not** the
goal — that work already exists via `EdgeStatus` for *current* state.

Layout per row:

```
┌────────────────────────────────────────────────────┐
│ ● node-gate-1     R1   ✓ → node-planner (eval: 3) │
│   state @ this phase: 12 keys • 1.4 KB             │
│   [ View state ]                                    │
└────────────────────────────────────────────────────┘
```

Clicking "View state" expands an inline `<pre>` of the JSON state — same look as
the existing "Current State" tab.

### A4 — Mount `ExecutionPanel` in the other two workflow entry points

Two sites:

1. **`MvpDebateView.svelte`** — already a workflow consumer. Mount
   `<ExecutionPanel sessionId={result.session_id} />` next to the existing
   activity log, behind a toggle button ("Execution trace").
2. **`InputComposerView.svelte`** — *if* the user runs a workflow from there.
   For now: lazy-mount when a workflow session is active (i.e. the page already
   has a `sessionId` prop from a prior run). No new buttons.

This is a copy-paste mount, not a refactor: the panel already has
`sessionId` as a prop and an internal `null` short-circuit when not provided.

### A5 — Extend `feedbackStore.logActivity` entries to include phase-snapshot events

Building on the QW-1 channel pattern, add one new event per `load(sessionId)`
completion:

- `kind: 'phase_snapshot'`, `level: 'info'`, `meta: { node_id, phase, decision? }`

This keeps the existing activity log a single timeline of "what the user
cared about" without needing a second component.

### A6 — Test pyramid: vitest (units) + a single Playwright component test

- **Unit:** store reducer (load/invalidate/load-while-inflight), helpers (URL
  construction, error mapping), and the `PhasesTab` rendering with a mocked store
- **Component:** Playwright `component` mode (already configured in
  `frontend/playwright/`) opens the panel in `MvpDebateView`, mocks the API,
  asserts the timeline rows + expand interaction

### A7 — No new dependencies, no new i18n keys

`i18n` strings for the panel and tab use the existing `execution.*` and
`workflow.*` namespaces. No new locale files.

---

## Files to Create / Modify

### 1. NEW: `frontend/src/lib/api/workflowExec.js` (helpers)

Two thin wrappers around `fetch`, modeled on the existing `apiFetch` pattern in
`frontend/src/lib/api/`:

```js
// frontend/src/lib/api/workflowExec.js
import { apiFetch } from '$lib/api/client.js';

/** @returns {Promise<Array<{ node_id: string, node_type: string, phase: number, round: number|null, state_size: number, created_at: string }>>} */
export async function getPhaseSnapshots(sessionId) {
  const res = await apiFetch(`/api/workflow_exec/${encodeURIComponent(sessionId)}/phase-snapshots`);
  if (!res.ok) throw new Error(`phase-snapshots: ${res.status}`);
  return res.json();
}

/** @returns {Promise<{ node_id: string, node_type: string, phase: number, round: number|null, state: object, created_at: string } | null>} */
export async function getPhaseSnapshotDetail(sessionId, nodeId) {
  const res = await apiFetch(`/api/workflow_exec/${encodeURIComponent(sessionId)}/phase-snapshots/${encodeURIComponent(nodeId)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`phase-snapshot-detail: ${res.status}`);
  return res.json();
}
```

### 2. NEW: `frontend/src/lib/stores/phaseSnapshotsStore.svelte.js`

Per the A2 shape above. ~80 lines.

### 3. NEW: `frontend/src/components/workflow/PhasesTab.svelte`

~120 lines. Props: `sessionId: string`. Internally calls
`phaseSnapshotsStore.load(sessionId)` on mount and on session change. Renders
timeline per A3. Each row is a `<button>` (a11y: `aria-expanded`).

### 4. EDIT: `frontend/src/components/blueprint/ExecutionPanel.svelte`

Add a third tab next to the existing "Node Output Log" and "Current State" tabs:

```
[ Node Output Log ] [ Current State ] [ Phases (N) ]
```

The `PhasesTab` is only rendered when the panel is open *and* there is a
`sessionId`. Default tab remains "Node Output Log" for backwards compatibility.

### 5. EDIT: `frontend/src/views/BlueprintCanvasView.svelte`

No change to the quick-win code in `00ad6bd`. Verify the panel mount point still
works after the tab-strip edit.

### 6. NEW: `frontend/src/components/workflow/PhaseSnapshotsWidget.svelte`

A smaller widget (~70 lines) for `InputComposerView` and the MvpDebate activity
sidebar. Shows the *first* snapshot only with a "View all phases →" link that
opens the full `PhasesTab` in a modal. Lazy-loads via the same store.

### 7. EDIT: `frontend/src/views/MvpDebateView.svelte`

Add an "Execution trace" toggle button next to the existing activity log. When
toggled on, render `<ExecutionPanel sessionId={currentSessionId} />` in a
side-by-side layout. The toggle is hidden until a `sessionId` is available.

### 8. EDIT: `frontend/src/views/InputComposerView.svelte`

Conditionally render `<PhaseSnapshotsWidget sessionId={…} />` in the right rail
when a session is active. No new state — uses the existing
`workflowSessionStore.sessionId` (already populated by the run flow).

### 9. EDIT: `frontend/src/lib/stores/feedbackStore.svelte.js` *(or wherever `logActivity` is defined)*

In `MvpDebateView`'s SSE handlers (or in a new `usePhaseSnapshotBridge` hook
called by `PhasesTab`), emit a `'phase_snapshot'` log entry the first time a
phase snapshot is loaded (per A5). Keep the existing `'gate'` and `'node'`
channels untouched.

### 10. NEW: `tests/frontend/phaseSnapshotsStore.test.js`

Covers:

- `load(sid)` populates list and detail map
- `load(sid)` while a load for the same `sid` is in-flight → reuses the promise
- `invalidate(sid)` resets the entry; next `load` re-fetches
- `load` failure sets `error` but does not throw

### 11. NEW: `tests/frontend/PhasesTab.test.js` (Vitest + `@testing-library/svelte`)

- Renders rows in the order returned by the API
- Empty state when no snapshots
- Expand/collapse on row click
- Loading skeleton during `load`

### 12. NEW: `tests/frontend/workflowExec.test.js`

- `getPhaseSnapshots` URL-encodes `sessionId` and parses JSON
- `getPhaseSnapshotDetail` returns `null` on 404
- Throws on 5xx

### 13. NEW: `frontend/playwright/execution-panel-phases.spec.ts`

- Mocks `/api/workflow_exec/{sid}/phase-snapshots` with 3 fixtures
- Opens MvpDebateView with `sessionId` set
- Toggles "Execution trace"
- Asserts: 3 rows in the Phases tab, expanding row 1 shows the JSON state

### 14. EDIT: locale files (`frontend/src/lib/i18n/locales/{en,de}.json`)

Add 4 keys under `workflow.*`:

- `workflow.phases.title` = "Phases"
- `workflow.phases.empty` = "No phase snapshots yet"
- `workflow.phases.viewState` = "View state"
- `workflow.execution.toggleTrace` = "Execution trace"

---

## Summary of All Changes

| # | Action | Path | Lines (est.) |
|---|--------|------|--------------|
| 1 | NEW | `frontend/src/lib/api/workflowExec.js` | ~25 |
| 2 | NEW | `frontend/src/lib/stores/phaseSnapshotsStore.svelte.js` | ~80 |
| 3 | NEW | `frontend/src/components/workflow/PhasesTab.svelte` | ~120 |
| 4 | EDIT | `frontend/src/components/blueprint/ExecutionPanel.svelte` | +30 |
| 5 | EDIT | `frontend/src/views/BlueprintCanvasView.svelte` | 0 (verify) |
| 6 | NEW | `frontend/src/components/workflow/PhaseSnapshotsWidget.svelte` | ~70 |
| 7 | EDIT | `frontend/src/views/MvpDebateView.svelte` | +25 |
| 8 | EDIT | `frontend/src/views/InputComposerView.svelte` | +15 |
| 9 | EDIT | `frontend/src/lib/stores/feedbackStore.svelte.js` | +10 |
| 10 | NEW | `tests/frontend/phaseSnapshotsStore.test.js` | ~80 |
| 11 | NEW | `tests/frontend/PhasesTab.test.js` | ~70 |
| 12 | NEW | `tests/frontend/workflowExec.test.js` | ~50 |
| 13 | NEW | `frontend/playwright/execution-panel-phases.spec.ts` | ~80 |
| 14 | EDIT | `frontend/src/lib/i18n/locales/{en,de}.json` | +8 each |

**Net:** ~750 LoC added, 0 LoC removed.

---

## Execution Order (3 PRs)

### PR-1 — Helpers + Store + Tabs (foundation)

1. `frontend/src/lib/api/workflowExec.js` (1)
2. `frontend/src/lib/stores/phaseSnapshotsStore.svelte.js` (2)
3. `frontend/src/components/workflow/PhasesTab.svelte` (3)
4. `frontend/src/components/blueprint/ExecutionPanel.svelte` (4) — add the third tab
5. `tests/frontend/workflowExec.test.js` (12)
6. `tests/frontend/phaseSnapshotsStore.test.js` (10)
7. `tests/frontend/PhasesTab.test.js` (11)

**Ship criterion:** Canvas-based workflow sessions show a populated "Phases"
tab in the ExecutionPanel. Other entry points unaffected.

### PR-2 — Cross-Entry-Point Mount

1. `frontend/src/components/workflow/PhaseSnapshotsWidget.svelte` (6)
2. `frontend/src/views/MvpDebateView.svelte` (7) — "Execution trace" toggle
3. `frontend/src/views/InputComposerView.svelte` (8) — widget mount
4. `frontend/src/lib/stores/feedbackStore.svelte.js` (9) — `phase_snapshot` channel
5. locale edits (14)

**Ship criterion:** Running an MVP-debate workflow from MvpDebateView shows
the same execution trace as the canvas path. The InputComposer rail widget
renders when a session is active.

### PR-3 — E2E Coverage

1. `frontend/playwright/execution-panel-phases.spec.ts` (13)

**Ship criterion:** `npm run test:e2e` passes for the new spec on CI.

---

## Mermaid: Data Flow

```mermaid
flowchart LR
  subgraph Backend
    API1[GET /phase-snapshots]
    API2[GET /phase-snapshots/{node_id}]
  end
  subgraph Frontend
    H[workflowExec.js helpers]
    S[phaseSnapshotsStore]
    PT[PhasesTab.svelte]
    W[PhaseSnapshotsWidget.svelte]
    EP[ExecutionPanel.svelte]
    MVP[MvpDebateView.svelte]
    ICV[InputComposerView.svelte]
    BCV[BlueprintCanvasView.svelte]
  end
  API1 -->|JSON| H
  API2 -->|JSON| H
  H --> S
  S --> PT
  S --> W
  PT --> EP
  W --> MVP
  W --> ICV
  EP --> BCV
  EP --> MVP
```

---

## Verification

### Per-PR

- `cd frontend && npm run lint` — clean
- `cd frontend && npm run test` — all vitest pass (existing 173 + new ~10)
- `cd frontend && npm run build` — vite build succeeds
- Manual smoke: start a workflow, open the panel, click Phases, expand a row,
  confirm JSON matches the audit log for that node

### End-to-end

- `cd frontend && npm run test:e2e` — new spec passes
- Visual review of:
  - `MvpDebateView` "Execution trace" toggle
  - `InputComposerView` rail widget
  - `BlueprintCanvasView` ExecutionPanel Phases tab

### Regression

- Existing 173 vitest pass
- Existing Playwright suite passes (run the full `npm run test:e2e`)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| `StateSnapshotStore` returns very large state JSONs | The timeline row only shows `state_size` + a hash; the expanded view lazy-loads the detail and shortens at 50 KB like `audit_logger` |
| `load()` called from many components for the same session | A2's in-flight promise map dedupes |
| Canvas panel tab order changes break muscle memory | Default tab remains "Node Output Log"; Phases is the *last* tab |
| `MvpDebateView` already has a busy right rail | The "Execution trace" toggle is *off* by default — opt-in |
| `InputComposerView` widget adds vertical height | Widget is collapsible (header-only when no `sessionId`) |

---

## Out of Scope / Follow-up

- **F1 — Persist "viewed snapshots" so the panel can highlight unseen phases.**
  Would need a small per-user table. Not required for visibility.
- **F2 — Inline diff between two phase snapshots.** Could ship a P5.5 if the
  timeline becomes a hot path. Currently `state_size` is a sufficient proxy.
- **F3 — Render the canvas graph at a past phase** (replay mode). The
  `StateSnapshotStore.get_by_node(...)` already returns enough state to do
  this, but it's a 2-3 day build and should be a separate plan.
- **F4 — Emit a `'phase_snapshot'` SSE event** so the timeline updates in
  real-time, not just on panel open. Nice-to-have; would require a backend
  change in `backend/workflow/nodes/moderator_nodes.py`.

---

## Estimated Effort

- PR-1: ~3 hours (helpers + store + tab + unit tests)
- PR-2: ~2 hours (mount sites + i18n)
- PR-3: ~2 hours (Playwright spec + CI wiring)

**Total: ~7 hours of focused work, shippable as 3 small PRs in 1 dev day.**
