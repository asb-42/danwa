# Phase Visual Grouping in Workflow Canvas

## Problem

The 5-phase debate template has 15+ agent nodes across 5 phases (Problem Framing, Position Building, Stress Testing, Integration, Closure), but the canvas shows them as a flat graph with no visual grouping or phase labeling. Users cannot see which agents belong to which phase.

## Current State

- `WorkflowNode` already has `parent_id: str | None` for phase container membership
- `wf-phase` is a valid node type in the workflow definition
- `PhaseConfig` has `name`, `color`, `description`, `roles`, `max_rounds`
- `WorkflowDefinition` has `phase_configs: dict[str, PhaseConfig]`
- The 5-phase template (`templates/five_phase_debate.json`) does NOT use `wf-phase` nodes — phases are only implicit in label text

## Solution

### Part 1: Template — Add wf-phase nodes

Add 5 `wf-phase` group nodes to the template and set `parent_id` on all agent nodes.

```json
{
  "id": "phase-1",
  "type": "wf-phase",
  "label": "Phase 1 — Problem Framing",
  "config": { "color": "#6366f1", "description": "Analyst, Creative Thinker, Socratic Questioner" },
  "position": { "x": 450, "y": 80 }
}
```

Agent nodes get `parent_id`:
```json
{
  "id": "analyst-1",
  "type": "wf-analyst",
  "parent_id": "phase-1",
  ...
}
```

Also update `phase_configs` in the workflow definition:
```json
"phase_configs": {
  "phase-1": { "name": "Problem Framing", "color": "#6366f1", "roles": ["analyst", "creative", "socratic-questioner"] },
  "phase-2": { "name": "Position Building", "color": "#8b5cf6", "roles": ["strategist", "expert-reviewer", "steel-manner"] },
  ...
}
```

### Part 2: Frontend — PhaseNode component

Create `frontend/src/components/workflow/nodes/PhaseNode.svelte`:
- Renders as a semi-transparent colored background rectangle
- Shows phase name as a header badge
- Uses the color from `phase_configs` or `config.color`
- Svelte Flow handles child node positioning within the group

Register as `phase` in `WorkflowCanvas.svelte` nodeTypes.

### Part 3: Frontend — Layout engine updates

Update `frontend/src/lib/workflow/layout.js`:
- ELK layout needs to handle group nodes (parents)
- Child nodes are laid out within their parent's bounds
- Phase nodes get a minimum size based on their children

### Part 4: Frontend — Workflow store integration

Update `frontend/src/lib/workflow/store.svelte.js`:
- When loading a workflow definition, create phase group nodes from `phase_configs`
- Set `parentId` on agent nodes based on `parent_id` from the workflow definition

### Part 5: Frontend — Runtime phase highlighting

During execution:
- Highlight the current phase (the phase containing the currently executing node)
- Show phase progress (e.g., "2/3 agents completed")
- Dim completed phases slightly

### Part 6: Backend — Workflow compiler passthrough

Ensure `WorkflowCompiler` passes `parent_id` through to the compiled workflow so the frontend can read it from the workflow definition API.

## Files to Modify

| File | Change |
|------|--------|
| `templates/five_phase_debate.json` | Add 5 wf-phase nodes, set parent_id on agents, add phase_configs |
| `templates/four_phase_debate.json` | Same pattern (if exists) |
| `frontend/src/components/workflow/nodes/PhaseNode.svelte` | NEW — group node component |
| `frontend/src/components/workflow/WorkflowCanvas.svelte` | Register PhaseNode in nodeTypes |
| `frontend/src/lib/workflow/layout.js` | Handle group node nesting in ELK layout |
| `frontend/src/lib/workflow/store.svelte.js` | Load phase nodes from workflow definition |
| `backend/workflow/workflow_compiler.py` | Ensure parent_id passes through |
| `backend/blueprints/workflow_models.py` | Already correct (no changes needed) |

## Implementation Order

1. Add wf-phase nodes + parent_id + phase_configs to templates
2. Create PhaseNode.svelte component
3. Register in WorkflowCanvas
4. Update layout engine for group nodes
5. Update store to load phase nodes
6. Add runtime phase highlighting
7. Commit + push

## Svelte Flow Group Nodes

Svelte Flow supports group nodes natively:
- A node with `type: 'group'` (or custom group type) acts as a container
- Child nodes reference their parent via `parentId`
- The group node renders as a background behind its children
- Children are positioned relative to the parent's origin

Reference: https://svelteflow.dev/examples/nodes/sub-flows
