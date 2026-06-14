# Workflow-Observability Plan — Review

**Plan under review:** [`plans/workflow-observability.md`](../plans/workflow-observability.md)
**Reviewer:** Claude Code (auto-review)
**Date:** 2026-06-14
**Verdict:** ✅ **Plan is fully implemented and still up to date.**
**Implementation commit:** `2a47340 feat: workflow observability — structured gate logging, phase checkpoints, visual trace`

---

## 1. Executive Summary

The plan defines three tightly coupled observability features for the LangGraph
workflow engine:

1. **Structured gate logging** — every gate (`route_conditional`) decision
   publishes a `gate.decision` SSE event and writes an audit-log row.
2. **State checkpointing per phase** — every gate is a natural phase boundary;
   a `phase_checkpoint` state snapshot is saved so the phase can be rehydrated.
3. **Visual trace (frontend)** — the SSE events drive (a) gate decision cards
   in the `ExecutionPanel` and (b) emerald/grey edge highlighting in the
   blueprint canvas.

All three features shipped together in commit [`2a47340`](../../gitnexus://repo/danwa/process/workflow-execution). The
implementation survives the subsequent P4.5+ refactors (audit logger loud,
pubsub loud, bounded interjection) without behavioural changes. The only
drift is a frontend component rename: the plan mentions
`WorkflowPipeline.svelte` / `PipelineEdge.svelte`, but those were replaced by
the newer `BlueprintCanvas` / `BlueprintCanvasView` system in the
[Phase-2 canvas migration](../plans/phase2-canvas-migration.md). The
architectural intent (edge highlighting with `.taken` / `.skipped` states) is
preserved verbatim.

Test coverage: **193 / 193** relevant tests pass
(`test_workflow_routers.py`, `test_workflow_compiler.py`,
`test_workflow_phases.py`, `test_workflow_templates.py`, `test_workflow.py`,
`test_audit_logger.py`, `test_audit_router.py`, `test_decision_mapping.py`,
`test_decision_topological_order.py`).

---

## 2. Architectural Decisions — Status Check

The plan makes five architectural decisions. Each is checked against the
current code.

| # | Decision (from plan) | Status | Evidence |
|---|----------------------|--------|----------|
| 1 | `route_conditional()` factory takes a `gate_node_id` so the router knows which gate fired | ✅ Present | [`workflow_routers.py:39`](../backend/workflow/workflow_routers.py:39) — `def route_conditional(conditions, gate_node_id="")` |
| 2 | `gate.decision` SSE event is published on every routing call (match and fallback) | ✅ Present | [`workflow_routers.py:115`](../backend/workflow/workflow_routers.py:115) — `_publish_gate_decision()` helper called at lines 69-78 (first match) and 100-109 (fallback) |
| 3 | The same event is also written to the audit log via `AuditLogger.log_gate_decision()` | ✅ Present | [`audit_logger.py:400`](../backend/workflow/audit_logger.py:400) — `log_gate_decision()` with full kw-only signature; called from [`workflow_routers.py:145`](../backend/workflow/workflow_routers.py:145) |
| 4 | `gate_node_factory` saves a `phase_checkpoint` snapshot on every gate evaluation | ✅ Present | [`moderator_nodes.py:404`](../backend/workflow/nodes/moderator_nodes.py:404) — `StateSnapshotStore().save(node_type="phase_checkpoint", node_id=f"phase:{node_id}")` |
| 5 | The snapshot store supports a `get_by_type()` query for the new endpoint | ✅ Present | [`state_snapshot.py:219`](../backend/workflow/state_snapshot.py:219) — `get_by_type(session_id, node_type)` method |
| 6 | `GET /{session_id}/phase-snapshots` returns metadata only; detail endpoint returns full state | ✅ Present | [`workflow_exec.py:905`](../backend/api/routers/workflow_exec.py:905) (list) and [`workflow_exec.py:932`](../backend/api/routers/workflow_exec.py:932) (detail with 404 on miss) |
| 7 | Frontend registers `gate.decision` in the SSE handler map | ✅ Present | [`workflowSSE.js:67`](../frontend/src/lib/workflowSSE.js:67) — `'gate.decision': 'onGateDecision'`; also in `namedEvents` at line 113 |
| 8 | `ExecutionPanel.svelte` renders a card per gate decision with ✅/❌ icon | ✅ Present | [`ExecutionPanel.svelte:383`](../frontend/src/components/blueprint/ExecutionPanel.svelte:383) — gate cards with `class:gate-passed` / `class:gate-failed` |
| 9 | The blueprint canvas highlights the chosen outgoing edge as "taken" (emerald) and other outgoing edges as "skipped" (grey) | ✅ Present | [`BlueprintCanvasView.svelte:823`](../frontend/src/views/BlueprintCanvasView.svelte:823) sets `edgeStatusMap[edge.id] = 'taken'` / `'skipped'`; CSS at [`BlueprintCanvas.svelte:715`](../frontend/src/components/blueprint/BlueprintCanvas.svelte:715) — `.edge-taken { stroke: #10b981 !important; }` |
| 10 | Both SSE publish and audit log are best-effort (errors swallowed at debug) | ✅ Present | [`workflow_routers.py:127-142`](../backend/workflow/workflow_routers.py:127) and [`workflow_routers.py:145-160`](../backend/workflow/workflow_routers.py:145) — both wrapped in `try/except Exception: logger.debug(..., exc_info=True)`. Same pattern as §4.5 / §4.10 |

**Conclusion:** All 10 architectural decisions from the plan are still
present in the code. No drift that would require an architectural change.

---

## 3. Implementation Review — File by File

### 3.1 Backend — Feature 1: Structured Gate Logging

#### [`backend/workflow/workflow_routers.py`](../backend/workflow/workflow_routers.py)

- `route_conditional(conditions, gate_node_id="")` factory at
  [`workflow_routers.py:39`](../backend/workflow/workflow_routers.py:39) accepts the
  optional `gate_node_id` (used to identify which gate fired in SSE/audit).
- Inner `_router` at line 56 reads `session_id` from state
  (`state.get("session_id", "")` at line 58).
- Helper `_publish_gate_decision` at line 115 publishes the SSE event and
  calls `get_audit_logger().log_gate_decision(...)`. Both calls are wrapped
  in independent `try/except` blocks so neither can break the other.
- The `_router` calls `_publish_gate_decision` twice: once for the first
  matching condition (lines 69-78) and once for the fallback path
  (lines 100-109).
- For gates with **feedback edges** (where the simple `route_conditional`
  factory is bypassed), a separate `_make_router(conds, fallback_target, gid)`
  is built in [`workflow_compiler.py:768`](../backend/workflow/workflow_compiler.py:768)
  and also calls `_publish_gate_decision` (lines 782-792 and 797-804).
  *This was not explicitly spelled out in the plan, but is required to keep
  the audit trail complete for feedback-loop workflows.*

#### [`backend/workflow/audit_logger.py`](../backend/workflow/audit_logger.py)

- New method `log_gate_decision()` at line 400 with full keyword-only
  signature: `session_id, workflow_id, workflow_version, gate_node_id,
  condition, result, chosen_target, fallback_used, all_evaluations=None`.
- Uses `event_type="gate_decision"`, `actor="gate"`, `node_id=gate_node_id`.
- Input hash: `_compute_hash({"condition": condition})`.
- Output hash: `_compute_hash({condition, result, chosen_target, fallback_used, all_evaluations})`.
- Output content: `_sanitize_content(output_data)` (truncated to 50 KB by
  the existing `_sanitize_content` helper).

### 3.2 Backend — Feature 2: State Checkpointing per Phase

#### [`backend/workflow/nodes/moderator_nodes.py`](../backend/workflow/nodes/moderator_nodes.py)

- After the gate's condition evaluation succeeds (line 405), a phase snapshot
  is saved with:
  - `node_id = f"phase:{node_id}"` (scoped under the `phase:` namespace)
  - `node_type = "phase_checkpoint"`
  - `round_number = current_round` (from gate context)
  - `state_dict = _serialize_state(dict(state))` (calls the existing
    `workflow_runner._serialize_state` helper)
- The save is wrapped in `try/except Exception: logger.debug(..., exc_info=True)`
  so a snapshot failure never breaks the gate's routing decision.
- Both `node_id` and `round_number` are part of the snapshot row, so a
  subsequent GET on `/{session_id}/phase-snapshots/{node_id:path}` can
  retrieve the exact checkpoint for a phase.

#### [`backend/workflow/state_snapshot.py`](../backend/workflow/state_snapshot.py)

- New method `get_by_type(session_id, node_type)` at line 219. Returns all
  rows for the session filtered by `node_type` (e.g. `"phase_checkpoint"`),
  ordered by `id ASC` (chronological).
- The method is read-only and uses the same connection lock as the rest of
  the store.

#### [`backend/api/routers/workflow_exec.py`](../backend/api/routers/workflow_exec.py)

- `GET /{session_id}/phase-snapshots` at line 905:
  - Calls `StateSnapshotStore().get_by_type(session_id, "phase_checkpoint")`
  - Returns **metadata only** (the response model is built from
    `id, node_id, node_type, round_number, created_at, state_keys`)
  - The `state_keys` is a list of top-level keys (not the full state) so the
    list endpoint stays cheap.
- `GET /{session_id}/phase-snapshots/{node_id:path}` at line 932:
  - Calls `StateSnapshotStore().get_by_node(session_id, node_id)`
  - Returns the full `state_dict` and all metadata
  - Returns `404` if the snapshot does not exist (handled by returning
    `None` and the router converting to a FastAPI HTTPException)
- The `:path` converter is needed because `node_id` can contain
  `phase:node-foo` (with the colon), and FastAPI's default str converter
  stops at the first slash.

### 3.3 Frontend — Feature 3: Visual Trace

#### [`frontend/src/lib/workflowSSE.js`](../frontend/src/lib/workflowSSE.js)

- `'gate.decision': 'onGateDecision'` registered in `eventHandlerMap`
  (line 67).
- `'gate.decision'` listed in the `namedEvents` array (line 113) so it gets
  attached via `addEventListener` (in addition to the `onGateDecision`
  handler lookup).

#### [`frontend/src/components/blueprint/ExecutionPanel.svelte`](../frontend/src/components/blueprint/ExecutionPanel.svelte)

- `onGateDecision` handler at line 106:
  - Pushes the gate decision into a local `gateDecisions` array.
  - Calls `onGateDecisionUpdate(gateNodeId, chosenTarget)` so the parent
    (`BlueprintCanvasView`) can mark the edge.
- Render block at line 383-385: each entry in `gateDecisions` is rendered
  as a card with `class:gate-passed={gd.result}` /
  `class:gate-failed={!gd.result}` plus a ✅ / ❌ icon.

#### [`frontend/src/views/BlueprintCanvasView.svelte`](../frontend/src/views/BlueprintCanvasView.svelte)

- Lines 823-837: when `onGateDecisionUpdate(gateNodeId, chosenTarget)` fires,
  the view iterates over all edges and:
  - Marks the edge whose `source === gateNodeId && target === chosenTarget`
    as `'taken'`.
  - Marks all other edges from the same gate as `'skipped'`.
  - Stores the mapping in `edgeStatusMap` (a Svelte writable store).
- This drives the edge styling live as gate decisions stream in.

#### [`frontend/src/components/blueprint/BlueprintCanvas.svelte`](../frontend/src/components/blueprint/BlueprintCanvas.svelte)

- CSS at line 715: `:global(.edge-taken) { stroke: #10b981 !important; }`
  (emerald), plus a matching `.edge-skipped` rule with reduced opacity.
- The `:global` modifier is needed because the edge is rendered inside an
  xyflow-injected SVG and the class is applied there.

#### [`frontend/src/lib/blueprint/edgeStatus.js`](../frontend/src/lib/blueprint/edgeStatus.js)

- Defines the 5-state model: `idle | active | completed | taken | skipped`.
- The `'taken' → 'edge-taken'` and `'skipped' → 'edge-skipped'` mappings
  keep the CSS class names in one place.

---

## 4. Test Coverage

The implementation ships with **3 dedicated tests** in
[`tests/backend/test_workflow_routers.py:70`](../tests/backend/test_workflow_routers.py:70):

| Test | What it verifies |
|------|------------------|
| `test_publishes_sse_and_audits` | A routing call publishes the correct `gate.decision` SSE payload **and** calls `log_gate_decision` with the right kwargs. |
| `test_swallow_sse_publish_error` | If the SSE publish raises, the error is caught at `DEBUG` level and does not propagate. |
| `test_swallow_audit_error` | If the audit log call raises, the error is caught at `DEBUG` level and does not propagate. |

Combined with the existing router behaviour tests
(`TestRouteConditionalFirstMatch`, `TestRouteConditionalErrors`,
`TestRouteConditionalPublishing`, `TestRouteConditionalEvaluations`), the
test surface is complete: first-match, fallback, safe-eval error handling,
publishing on both match and fallback, evaluation records, and best-effort
error swallowing for both transports.

**Run:** `pytest tests/backend/test_workflow_routers.py -q` → **193 / 193
pass** across the affected test modules.

---

## 5. Architectural Drift — Frontend Component Rename

The plan's "Files to Modify" table lists:

```
frontend/src/components/workflow/WorkflowPipeline.svelte
frontend/src/components/workflow/pipeline/PipelineEdge.svelte
```

These files do **not exist** in the current tree. The implementation
delivered the visual trace in:

```
frontend/src/components/blueprint/ExecutionPanel.svelte
frontend/src/views/BlueprintCanvasView.svelte
frontend/src/components/blueprint/BlueprintCanvas.svelte
frontend/src/lib/blueprint/edgeStatus.js
```

**Why the rename happened:** the project migrated from a
`WorkflowPipeline` component (the Phase-1 implementation) to a
`BlueprintCanvas` system (the [Phase-2 canvas migration](../plans/phase2-canvas-migration.md))
in between the plan being written and the plan being implemented. The
blueprint system uses xyflow / Svelte for the graph view and supports a
5-state edge model (`idle | active | completed | taken | skipped`),
which is exactly what the plan's "Visual Trace" feature needs.

**Is this a regression?** No. The architectural intent — gate decision
cards + edge highlighting with `.taken` / `.skipped` CSS classes — is
preserved verbatim. The component rename is purely cosmetic; the
behavioural contract is identical. The plan should be updated to reflect
the new file names so future readers aren't confused.

**Recommendation:** Update the "Files to Modify" table in the plan to
list the blueprint-system files. No code change required.

---

## 6. Follow-up Work Required

**None.** The plan is fully implemented, tested, and integrated with the
newer P4.5+ refactors (audit logger loud, pubsub loud) without behavioural
change. The only suggested action is the cosmetic update to the plan's
file table noted in §5.

---

## 7. Appendix — Test Run Output

```
$ pytest tests/backend/test_workflow_routers.py \
         tests/backend/test_workflow_compiler.py \
         tests/backend/test_workflow_phases.py \
         tests/backend/test_workflow_templates.py \
         tests/backend/test_workflow.py \
         tests/backend/test_audit_logger.py \
         tests/backend/test_audit_router.py \
         tests/backend/test_decision_mapping.py \
         tests/backend/test_decision_topological_order.py -q

193 passed in 4.21s
```

---

## 8. Files Reviewed

- [`plans/workflow-observability.md`](../plans/workflow-observability.md) — the plan (259 lines)
- [`backend/workflow/workflow_routers.py`](../backend/workflow/workflow_routers.py) — `route_conditional`, `_publish_gate_decision`
- [`backend/workflow/workflow_compiler.py`](../backend/workflow/workflow_compiler.py) — `gate_node_id` plumbing, `_make_router` for feedback
- [`backend/workflow/audit_logger.py`](../backend/workflow/audit_logger.py) — `log_gate_decision` method
- [`backend/workflow/nodes/moderator_nodes.py`](../backend/workflow/nodes/moderator_nodes.py) — `gate_node_factory`, phase snapshot
- [`backend/workflow/state_snapshot.py`](../backend/workflow/state_snapshot.py) — `get_by_type` method
- [`backend/api/routers/workflow_exec.py`](../backend/api/routers/workflow_exec.py) — `GET /phase-snapshots` endpoints
- [`frontend/src/lib/workflowSSE.js`](../frontend/src/lib/workflowSSE.js) — `gate.decision` registration
- [`frontend/src/components/blueprint/ExecutionPanel.svelte`](../frontend/src/components/blueprint/ExecutionPanel.svelte) — gate cards
- [`frontend/src/views/BlueprintCanvasView.svelte`](../frontend/src/views/BlueprintCanvasView.svelte) — edge status updates
- [`frontend/src/components/blueprint/BlueprintCanvas.svelte`](../frontend/src/components/blueprint/BlueprintCanvas.svelte) — `.edge-taken` CSS
- [`frontend/src/lib/blueprint/edgeStatus.js`](../frontend/src/lib/blueprint/edgeStatus.js) — 5-state edge model
- [`tests/backend/test_workflow_routers.py`](../tests/backend/test_workflow_routers.py) — `TestPublishGateDecision` (3 tests)
- Git: `2a47340 feat: workflow observability — structured gate logging, phase checkpoints, visual trace`
