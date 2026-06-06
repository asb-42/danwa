# Audit Trail UX Improvement

## Problem Statement

The audit trail for workflow debates has three UX issues:
1. **Round always "—"**: `_transform_workflow_audit_events` in `audit.py` hardcodes `"round": None`
2. **Phase missing**: Neither API endpoint provides phase info (e.g. "Phase 1 — Strategists")
3. **Content is raw JSON**: `output_content` stores the full state update dict as JSON — includes `current_draft`, `node_outputs`, `messages` — unreadable even for technical users

## Data Flow Analysis

```
Audit Logger (SQLite)
  ├── output_content = json.dumps(node_fn_return_value)
  │     For agent nodes: {"current_draft": "...", "node_outputs": [{node_id, round, content, ...}], ...}
  │     For gate nodes:  {"gate_decision": {...}, ...}
  │     For input node:  {"context": "...", ...}
  │
  ├── API: workflow_exec.py /{session_id}/audit-log
  │     Returns raw fields — no round, no phase, no content formatting
  │
  └── API: audit.py /api/v1/audit/{debate_id}
        _transform_workflow_audit_events hardcodes round: None
        Passes raw output_content as "content"
```

## Solution Architecture

### Phase 1: Backend — Shared Audit Enrichment Helpers

Add two new helper functions to `backend/workflow/report_generator.py`:

#### `_build_audit_context_map(session_id: str) -> dict`

Builds `node_id → {round, phase, role_type_name}` from the state snapshot.

Data sources:
- `state["node_outputs"]` → each has `node_id` + `round` → build `node_id → round`
- `state["node_configs"]` → each has `role_type_name` → build `node_id → role_type_name`
- `state["node_sequence"]` → ordered node IDs → build `node_id → phase_index`
- Workflow definition `phase_configs` (loaded via `workflow_id` from repo) → map phase node IDs to names

Phase derivation logic:
- Walk `node_sequence` in order
- When encountering a `wf-phase` node, look up its name from `phase_configs`
- All subsequent non-phase nodes belong to that phase until the next `wf-phase`

#### `_format_audit_content(output_content: str, event_type: str) -> str`

Parses the raw JSON and extracts human-readable text:

- `node_completed` for agent nodes: Extract `node_outputs[0].content` (the actual LLM output)
- `node_completed` for gate nodes: Extract gate decision summary
- `node_completed` for input/complete nodes: Extract context/output text
- `node_started`: Return empty (no content yet)
- `node_failed`: Show error message
- Fallback: Try to parse JSON and extract any `content` field, else show truncated raw

### Phase 2: Backend — Enrich API Endpoints

#### `workflow_exec.py` — `get_workflow_audit_log`

Add to each entry:
```python
{
    "round": ctx.get("round"),          # int or None
    "phase": ctx.get("phase", ""),      # str e.g. "Phase 1 — Strategists"
    "content_formatted": _format_audit_content(output_content, event_type),
    # ... existing fields ...
}
```

#### `audit.py` — `_transform_workflow_audit_events`

Change from hardcoded `"round": None` to use context map:
```python
{
    "round": ctx.get("round"),
    "phase": ctx.get("phase", ""),
    "content": _format_audit_content(output_content, event_type),
    # ... existing fields ...
}
```

### Phase 3: Frontend — Display Improvements

#### `AuditView.svelte`

- Add Phase column between Round and Agent
- Content column: show `event.content` which is now formatted text (truncated preview + expandable full text already works)

#### `AuditTrail.svelte`

- Add Round column (already has the data from workflow_exec API)
- Add Phase column
- Show `llm_profile_name` instead of raw `llm_profile_id` in expanded detail

#### `SessionAuditTab.svelte`

- Add phase to filter options
- Add phase to CSV export

## Files to Modify

| File | Change |
|------|--------|
| `backend/workflow/report_generator.py` | Add `_build_audit_context_map()` + `_format_audit_content()` |
| `backend/api/routers/workflow_exec.py` | Enrich audit log entries with round, phase, formatted content |
| `backend/api/routers/audit.py` | Use context map in `_transform_workflow_audit_events` |
| `frontend/src/views/AuditView.svelte` | Add Phase column |
| `frontend/src/components/AuditTrail.svelte` | Add Round + Phase columns, show llm_profile_name |
| `frontend/src/components/workflow/SessionAuditTab.svelte` | Add phase filter + CSV export |

## Implementation Order

1. `_build_audit_context_map()` helper
2. `_format_audit_content()` helper
3. `workflow_exec.py` enrichment
4. `audit.py` enrichment
5. Frontend `AuditView.svelte`
6. Frontend `AuditTrail.svelte`
7. Frontend `SessionAuditTab.svelte`
8. Ruff format + commit + push
