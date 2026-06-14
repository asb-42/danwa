# Workflow-Observability — UX Visibility Gap

**Date:** 2026-06-14
**Follow-up to:** [`2026-06-14_workflow-observability-review.md`](../reports/2026-06-14_workflow-observability-review.md)
**Verdict:** The backend code is correct, but the **frontend has no
exposure** of the observability data. The user-visible gap is real.

---

## TL;DR

The review at [`2026-06-14_workflow-observability-review.md`](../reports/2026-06-14_workflow-observability-review.md)
confirmed that the backend pipeline is in place:
1. `route_conditional()` publishes `gate.decision` SSE events
   ([`backend/workflow/workflow_routers.py:39`](../backend/workflow/workflow_routers.py:39)).
2. The frontend registers the event and the panel populates `gateDecisions`
   ([`frontend/src/components/blueprint/ExecutionPanel.svelte:106`](../frontend/src/components/blueprint/ExecutionPanel.svelte:106)).
3. The edge highlighting CSS exists
   ([`frontend/src/components/blueprint/BlueprintCanvas.svelte:715`](../frontend/src/components/blueprint/BlueprintCanvas.svelte:715)).

**However, three things prevent the data from reaching the user's eyes:**

| # | Gap | Where | Impact |
|---|-----|-------|--------|
| 1 | **Phase-snapshot API is never called by the frontend** | Backend [`GET /phase-snapshots`](../backend/api/routers/workflow_exec.py:905) endpoint exists; `getPhaseSnapshots` does not exist in the frontend | The "state per phase" feature is invisible in the UI |
| 2 | **The execution panel only shows inside one view (`BlueprintCanvasView`)** | [`BlueprintCanvasView.svelte:801`](../frontend/src/views/BlueprintCanvasView.svelte:801) — `<ExecutionPanel ...>` rendered here, but not in `MvpDebateView` / `InputComposerView` | Users entering from MVP-Debate or Input-Composer never see the panel |
| 3 | **The blueprint canvas is not visible while a workflow is running** | Canvas is in edit mode; the user is in `MvpDebateView` / `InputComposerView`, not in `BlueprintCanvasView` | Even when edges are highlighted, the user never sees the canvas |

Plus one cosmetic gap that explains why "not much is visible":

| # | Gap | Where | Impact |
|---|-----|-------|--------|
| 4 | **Gate-decision cards are buried under "Node Output Log"** | [`ExecutionPanel.svelte:381`](../frontend/src/components/blueprint/ExecutionPanel.svelte:381) — `🔀 Gate Decisions` h4 appears *after* the node-output section | User has to scroll past many node-output cards to see gate decisions |
| 5 | **The "View State" button is the only way to see live state** | [`ExecutionPanel.svelte:419`](../frontend/src/components/blueprint/ExecutionPanel.svelte:419) — `{t('workflow.execution.viewState')}` — no per-phase state comparison, just current state | Phase-snapshot API (gap #1) is unused |

So the answer to *"is this a deeper issue?"* is **yes** — the backend is
fine, but the frontend wiring is incomplete. The data is generated, the
data is transmitted, but the data is never *consumed* for visual
presentation beyond the side panel cards.

---

## Detailed Diagnosis

### Gap 1: Phase-snapshot API has no consumer

The plan's "Feature 2" deliverable was the API; the plan implicitly
assumed the frontend would show the snapshots somewhere (a panel, a
modal, an inspector). But the API is **unused** in the frontend:

```
$ grep -r "phase-snapshots\|getPhaseSnapshots" frontend/src
(no matches)
```

**What should be built** (not in scope of the current bug fix, but worth
naming): a "Phases" tab in the panel that lists each `phase_checkpoint`
with its state keys and a click-through to the full snapshot. This
delivers the "state per phase" promise of Feature 2.

### Gap 2: ExecutionPanel is only mounted in BlueprintCanvasView

The panel exists, but only one of the three workflow-execution entry
points actually mounts it:

| Entry point | Mounts `ExecutionPanel`? |
|-------------|--------------------------|
| [`BlueprintCanvasView.svelte:801`](../frontend/src/views/BlueprintCanvasView.svelte:801) | ✅ Yes |
| [`MvpDebateView.svelte`](../frontend/src/views/MvpDebateView.svelte) | ❌ No — uses `workflowPipelineAdapter.svelte.js` |
| [`InputComposerView.svelte:537`](../frontend/src/views/InputComposerView.svelte:537) | ❌ No — uses `DebateExecutionDisplay` instead |

`MvpDebateView` does have an SSE connection (via
`createWorkflowSSE(sid, {...})` at line 318) but it only handles a
handful of events; `gate.decision` is **not** in its handler set. So
gate decisions are received by the SSE connection but silently dropped
on the floor.

`InputComposerView` uses `DebateExecutionDisplay` which is a
post-hoc-results display, not a live execution panel.

**Result:** If the user runs the workflow from MVP-Debate or
Input-Composer, the panel — and therefore the gate cards, the
edge highlighting, and the phase snapshots — is never shown.

### Gap 3: Canvas is in edit mode, not execution mode

The blueprint canvas has a `mode` field on its store
([`store.svelte.js:30`](../frontend/src/lib/blueprint/store.svelte.js:30): `mode = $state('blueprint')`).
The mode is *not* switched to `'workflow'` automatically when a
workflow starts. The user has to:

1. Be in `BlueprintCanvasView` (Gap 2 blocker)
2. Manually switch the canvas to workflow mode (or have it switched
   automatically by the parent)
3. See the canvas at all while a workflow is running (the panel opens
   *over* the canvas as a side panel, but the canvas still has to be
   visible)

**Quick UX fix:** When `ExecutionPanel` becomes visible, the parent
should switch the canvas to workflow mode and ensure the canvas is
visible behind the panel. The panel is `position: absolute; right: 0;
width: 360px;` so it does *not* cover the canvas; the canvas just has
to actually be there.

### Gap 4: Gate-decision cards are scrolled off

The panel renders output sections in this order:

1. Status bar (running / paused / …)
2. Consensus + round counter
3. Node Output Log (this is **long** — one card per node, with full
   text content)
4. **🔀 Gate Decisions** (one card per gate) — *buried here*
5. View State button

For a typical debate with 5 phases × 3 agents = 15 node outputs, the
gate decisions are off-screen by default. The user has to scroll.

**Quick UX fix:** Move "🔀 Gate Decisions" above "Node Output Log", or
make the panel show gate decisions in a sticky right rail / popover
that doesn't scroll with the output log.

### Gap 5: State view is current-state only

The "View State" button shows the *current* workflow state. The
phase-snapshot API (Gap 1) is the way to see *historical* state at each
phase boundary. With Gap 1 unresolved, there is no UI to consume the
phase snapshots.

---

## Quick Wins (priority order)

| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| 1 | Add `gate.decision` to `MvpDebateView`'s SSE handler set | 5 min | Makes gate decisions visible from MVP-Debate entry point |
| 2 | Move gate cards above node-output log in `ExecutionPanel` | 5 min | Makes gate decisions visible without scrolling |
| 3 | Auto-switch canvas to workflow mode when panel opens | 10 min | Makes edge highlighting actually visible |
| 4 | Add `onGateDecisionUpdate` to `InputComposerView` and the `DebateExecutionDisplay` | 30 min | Enables edge highlighting from Input Composer |
| 5 | Add "Phases" tab in `ExecutionPanel` that calls `GET /phase-snapshots` | 2 h | Delivers the full Feature 2 promise |

Items 1-3 are pure CSS / handler-list changes and could ship in a
single small PR. Item 5 is the real Feature 2 deliverable that the
plan promised.

---

## Conclusion

The plan was implemented faithfully and the backend pipeline is
complete. The UX gap is real and is the expected outcome of the plan
only specifying *backend* deliverables (SSE event, audit log, phase
snapshot, API endpoint) and *frontend* deliverables that focus on the
panel and canvas inside `BlueprintCanvasView` only.

The architectural intent — **make gate decisions and phase state
visible to the user** — is partially fulfilled:

- ✅ Gate decisions are received from SSE.
- ✅ Gate decisions are stored in `gateDecisions[]`.
- ✅ Gate decisions are rendered as cards in the panel.
- ⚠️ The panel is only visible in 1 of 3 entry points.
- ⚠️ The cards are scrolled off in most workflows.
- ⚠️ Edge highlighting exists but the canvas is rarely visible.
- ❌ Phase snapshots are produced but never consumed by the UI.

The plan should be extended with a "Phase 5: UX exposure" section
listing the gaps above as explicit work items. The 4 quick wins
(items 1-3) are enough to make the existing observability visible to
all users; item 5 is needed to complete the Feature 2 promise.
