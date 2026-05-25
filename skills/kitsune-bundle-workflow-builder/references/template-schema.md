# Workflow Template Schema Reference

## Directory Structure

```
modules/workflows/workflow-tpl-{name}/
├── manifest.json    # Required
└── profile.json     # Required (profile_format=json)
```

## manifest.json

```json
{
  "schema_version": "2.0.0",
  "module_id": "workflow-tpl-{name}",
  "name": { "en": "Template Display Name" },
  "version": "1.0.0",
  "type": "workflow-template",
  "category": "workflows",
  "profile_file": "profile.json",
  "profile_format": "json",
  "files": []
}
```

## profile.json

```json
{
  "id": "tpl-{name}",
  "name": "Template Display Name",
  "description": "What this template does.",
  "category": "system",
  "tags": ["debate", "multi-agent", "multi-phase"],
  "template_data": {
    "nodes": [],
    "edges": [],
    "entry_point": "",
    "termination_conditions": []
  },
  "placeholders": [],
  "is_system": true
}
```

## Template Data: Nodes

Each node in `template_data.nodes` is:

```json
{
  "id": "unique-node-id",
  "type": "wf-{type}",
  "label": "Display Label",
  "position": { "x": number, "y": number },
  "agent_blueprint_id": "{{placeholder_key}}" | null,
  "bundle_id": "bundle-{role}" | null,
  "parent_id": "phase-node-id" | null,
  "config": {}
}
```

### Node Types

| Type | Purpose | Key Fields |
|---|---|---|
| `wf-input` | Topic input for the debate | None |
| `wf-initialize` | Initialize context node | None |
| `wf-phase` | Phase container (groups agents) | `config.name`, `config.max_rounds`, `config.objective` |
| `wf-agent` | Generic bundle-based agent | `bundle_id` (required) |
| `wf-gate` | Decision gate (consensus check) | `config.condition` |
| `wf-output` | Final output / result | None |

**Critical rule**: For templates with concrete bundle references (not `{{placeholders}}`), use `bundle_id` directly:
```json
{ "id": "analyst-1", "type": "wf-agent", "bundle_id": "bundle-analyst", ... }
```

For templates that should prompt the user to select a blueprint, use `{{placeholder}}`:
```json
{ "id": "agent-1", "type": "wf-agent", "agent_blueprint_id": "{{my_blueprint}}", ... }
```

### Phase Nodes

Phase nodes are container nodes. Agents within a phase set `parent_id` to the phase node's ID:
```json
{
  "id": "phase-1",
  "type": "wf-phase",
  "label": "Phase 1: Analysis",
  "position": { "x": 0, "y": 0 },
  "config": {
    "name": "Analysis",
    "max_rounds": 3,
    "objective": "Analyze the topic from multiple angles"
  }
}
```

Agents within a phase:
```json
{
  "id": "analyst-1",
  "type": "wf-agent",
  "bundle_id": "bundle-analyst",
  "parent_id": "phase-1",
  "position": { "x": 300, "y": 100 }
}
```

Phase nodes have a fixed width of ~700px and height of ~300px. Position agents vertically stacked within (y ~100, ~250, ~400).

## Template Data: Edges

```json
{
  "id": "e-unique",
  "source": "source-node-id",
  "target": "target-node-id",
  "type": "sequential" | "conditional" | "feedback" | "interjection",
  "condition": "expression" | null,
  "label": "Optional label"
}
```

### Edge Types and When to Use

| Type | Usage |
|---|---|
| `sequential` | Default flow between nodes. Output of source → input of target. |
| `feedback` | Loop back to an earlier node (e.g., moderator → strategist for next round). |
| `conditional` | Branching based on a condition. Only from `wf-gate` nodes. Requires `condition` field. |
| `interjection` | User injection point. |

### Standard Debate Pattern

```
input → init → agent1 → gate → output
                → agent2 ↗
```

Edges:
- `input → init`: sequential
- `init → agent1`: sequential
- `init → agent2`: sequential
- `agent1 → gate`: sequential
- `agent2 → gate`: sequential
- `gate → agent1`: feedback (loop for another round)
- `gate → output`: conditional (when consensus reached)
- `output → agent1`: feedback (next round)

### Multi-Phase Pattern

```
Phase 1             Phase 2             Phase 3
input → init → phase-1 → gate-1 → phase-2 → gate-2 → phase-3 → output
                agent1↔    ↗     agent4↔    ↗     agent7↔
                agent2↔  /
                agent3↔ /
```

Within each phase, agents run in parallel (init → agent1, agent2, agent3 all sequential). Between phases, a gate checks if the phase objective is met.

## Template Data: Termination Conditions

```json
"termination_conditions": [
  { "type": "max_rounds", "value": 5, "description": "Maximum total debate rounds" },
  { "type": "consensus_reached", "value": 0.9, "description": "Consensus threshold" }
]
```

Common conditions:
- `max_rounds`: Hard limit on rounds (integer)
- `consensus_reached`: Agreement threshold (float 0.0-1.0)

## Template Data: Entry Point

```json
"entry_point": "input-1"
```

Should point to the first node in the workflow (usually a `wf-input` or `wf-initialize` node).

## Placeholders

For templates that need user input at instantiation time:

```json
"placeholders": [
  {
    "key": "placeholder_name",
    "type": "blueprint_ref" | "string" | "integer" | "float",
    "default": "optional default value",
    "description": "What this placeholder does"
  }
]
```

Use `{{placeholder_name}}` in `template_data` to reference placeholders. The instantiation engine deep-replaces all `{{key}}` with the user's values.

Use placeholders when:
- You want the user to pick an agent blueprint at instantiation time
- You have configurable parameters (max rounds, thresholds)
- The template needs user-specific data

Do NOT use placeholders when:
- You have concrete bundle references (bundles are filesystem modules, always available)
- The values are hard-coded structural elements

## Layout Tips

### Spacing Convention
- X spacing: nodes spaced ~250-300px apart horizontally
- Y spacing: parallel nodes spaced ~150-200px apart vertically
- Phase containers: x=0, y=phase_number * 350

### Phase Layout
```
phase-1 (x: 0, y: 0, width: 700, height: 300)
  ├── agent-1 (x: 300, y: 80)
  ├── agent-2 (x: 300, y: 220)
  └── agent-3 (x: 300, y: 360)

phase-2 (x: 0, y: 400, width: 700, height: 300)
  ├── agent-4 (x: 300, y: 480)
  ├── agent-5 (x: 300, y: 620)
  └── agent-6 (x: 300, y: 760)
```
