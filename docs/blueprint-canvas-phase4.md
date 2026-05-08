# Blueprint Canvas — Phase 4: Workflow-Builder Preparation

## Overview

Phase 4 extends the Blueprint Canvas with workflow-building capabilities. It introduces a central node/edge registry, workflow-specific node types, a `WorkflowDefinition` backend model, a compiler service stub, and a mode switcher — all without breaking Phase 3 functionality.

## Architecture

### Node Registry Pattern

All node and edge types are registered through a central registry ([`frontend/src/lib/blueprint/registry.js`](../frontend/src/lib/blueprint/registry.js)). This replaces hardcoded `nodeTypes`/`edgeTypes` maps with a dynamic, extensible system.

```
registerAll.js  →  registry.registerNode(type, component, meta)
                →  registry.registerEdge(type, component, meta)

BlueprintCanvas →  registry.getNodeTypes()   → Svelte Flow nodeTypes
                →  registry.getEdgeTypes()   → Svelte Flow edgeTypes
Palette         →  registry.getNodesByCategory('asset')
                →  registry.getNodesByCategory('workflow')
```

### Mode Switcher

The canvas supports two modes:

| Mode | Description | Active Nodes | Active Edges |
|------|-------------|-------------|--------------|
| **Blueprint** | Design agent configurations | Asset nodes (4) | Semantic edges (4) |
| **Workflow** | Build debate workflows | Asset + Workflow nodes (9) | Semantic + Control flow edges (7) |

Switching from Workflow → Blueprint mode filters out workflow-only nodes and edges.

### Edge Type Classification

| Category | Edges | Visual Style |
|----------|-------|-------------|
| **Semantic** | `uses_llm`, `implements_role`, `prompted_by`, `overrides_prompt` | Colored solid (from Phase 3) |
| **Control Flow** | `sequential`, `conditional`, `interjection` | Indigo solid / Amber dashed / Rose dotted |

### Data Flow: Blueprint → Workflow

```
AgentBlueprint (catalog)  ←── referenced by ──  WorkflowDefinition.node_blueprint_map
       │                                                    │
       ├── llm_profile_id ──→ BlueprintLLMProfile           ├── execution_order
       ├── role_definition_id ──→ RoleDefinition             ├── conditional_edges
       └── prompt_template_id ──→ PromptTemplate (optional)  └── interjection_points
```

## Backend

### New Files

| File | Purpose |
|------|---------|
| [`backend/blueprints/workflow_models.py`](../backend/blueprints/workflow_models.py) | `WorkflowDefinition`, `ConditionalEdge`, `InterjectionPoint` Pydantic models |
| [`backend/blueprints/compiler.py`](../backend/blueprints/compiler.py) | `CompilerService` stub — validates blueprint references |

### Modified Files

| File | Changes |
|------|---------|
| [`backend/blueprints/migrations.py`](../backend/blueprints/migrations.py) | Schema v2: `workflow_definitions` table, `schema_version.description` column |
| [`backend/blueprints/repository.py`](../backend/blueprints/repository.py) | `save/get/list/delete_workflow_definition()` methods |
| [`backend/api/routers/blueprints.py`](../backend/api/routers/blueprints.py) | 6 new endpoints under `/workflows` |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/blueprints/workflows` | List all workflow definitions (paginated) |
| `GET` | `/api/v1/blueprints/workflows/{id}` | Get single workflow definition |
| `POST` | `/api/v1/blueprints/workflows` | Create workflow definition |
| `PUT` | `/api/v1/blueprints/workflows/{id}` | Update workflow definition |
| `DELETE` | `/api/v1/blueprints/workflows/{id}` | Delete workflow definition |
| `POST` | `/api/v1/blueprints/workflows/{id}/compile` | Compile (validate) workflow |

### SQLite Schema (v2)

```sql
CREATE TABLE workflow_definitions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    canvas_layout_id TEXT,
    execution_order_json TEXT NOT NULL DEFAULT '[]',
    conditional_edges_json TEXT NOT NULL DEFAULT '[]',
    interjection_points_json TEXT NOT NULL DEFAULT '[]',
    node_blueprint_map_json TEXT NOT NULL DEFAULT '{}',
    tags_json TEXT NOT NULL DEFAULT '[]',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (canvas_layout_id) REFERENCES canvas_layouts(id) ON DELETE SET NULL
);
```

### Compiler Service

The [`CompilerService`](../backend/blueprints/compiler.py) validates:

1. All referenced `AgentBlueprint`s exist and are active
2. All `LLMProfile`s referenced by blueprints exist
3. All `RoleDefinition`s referenced by blueprints exist
4. `execution_order` references valid node IDs
5. Conditional edges reference valid nodes
6. Interjection points reference valid nodes

Returns a [`CompilationResult`](../backend/blueprints/compiler.py:33) with `is_valid`, `resolved_agents`, `errors`, and `warnings`.

## Frontend

### New Files

| File | Purpose |
|------|---------|
| [`frontend/src/lib/blueprint/registry.js`](../frontend/src/lib/blueprint/registry.js) | Central node/edge type registry |
| [`frontend/src/lib/blueprint/registerAll.js`](../frontend/src/lib/blueprint/registerAll.js) | Registers all 11 node types + 7 edge types |
| [`frontend/src/components/blueprint/nodes/WorkflowNode.svelte`](../frontend/src/components/blueprint/nodes/WorkflowNode.svelte) | Workflow node with role-based coloring |
| [`frontend/src/components/blueprint/edges/SequentialEdge.svelte`](../frontend/src/components/blueprint/edges/SequentialEdge.svelte) | Indigo solid edge |
| [`frontend/src/components/blueprint/edges/ConditionalEdge.svelte`](../frontend/src/components/blueprint/edges/ConditionalEdge.svelte) | Amber dashed edge with condition label |
| [`frontend/src/components/blueprint/edges/InterjectionEdge.svelte`](../frontend/src/components/blueprint/edges/InterjectionEdge.svelte) | Rose dotted edge |
| [`frontend/src/components/blueprint/PaletteCategory.svelte`](../frontend/src/components/blueprint/PaletteCategory.svelte) | Reusable palette category section |
| [`frontend/src/components/blueprint/ModeSwitcher.svelte`](../frontend/src/components/blueprint/ModeSwitcher.svelte) | Blueprint/Workflow toggle |

### Modified Files

| File | Changes |
|------|---------|
| [`frontend/src/components/blueprint/Palette.svelte`](../frontend/src/components/blueprint/Palette.svelte) | Registry-based palette with categories |
| [`frontend/src/lib/blueprint/store.svelte.js`](../frontend/src/lib/blueprint/store.svelte.js) | `mode` state + `setMode()` method |
| [`frontend/src/lib/blueprint/validation.js`](../frontend/src/lib/blueprint/validation.js) | Mode-aware connection validation |
| [`frontend/src/components/blueprint/BlueprintCanvas.svelte`](../frontend/src/components/blueprint/BlueprintCanvas.svelte) | Registry-based types + ModeSwitcher |
| [`frontend/src/lib/blueprint/api.js`](../frontend/src/lib/blueprint/api.js) | 6 workflow API functions |
| [`frontend/src/lib/i18n/loaders/en.js`](../frontend/src/lib/i18n/loaders/en.js) | ~30 Phase 4 translation keys |
| [`frontend/src/lib/i18n/loaders/de.js`](../frontend/src/lib/i18n/loaders/de.js) | ~30 Phase 4 German translations |

### Workflow Node Roles

| Role | Color | Icon |
|------|-------|------|
| Strategist | Violet | 🎯 |
| Critic | Red | 🔍 |
| Optimizer | Amber | ⚡ |
| Moderator | Emerald | 🛡️ |
| User Input | Indigo | 👤 |

### Inactive Workflow Nodes

Workflow nodes in the palette are registered with `active: false` — they render with reduced opacity and a "Soon" badge. This prepares the UI for Phase 5 activation without enabling premature interaction.

## Tests

### Model Tests ([`tests/backend/test_blueprints.py`](../tests/backend/test_blueprints.py))

- `TestWorkflowDefinition` — model creation, defaults, validation (duplicate execution_order, empty name)
- `TestBlueprintRepositoryWorkflowDefinitions` — CRUD, pagination, roundtrip for conditional edges and interjection points
- `TestCompilerService` — valid workflow, missing blueprint/LLM/role, invalid execution_order/edges/interjections, inactive blueprint warning, empty workflow

### API Tests ([`tests/backend/test_blueprint_api.py`](../tests/backend/test_blueprint_api.py))

- `TestWorkflowDefinitionAPI` — full CRUD, pagination, conflict, not-found, minimal workflow, validation errors
- `TestCompilerAPI` — compile valid/invalid workflows via HTTP endpoint
- `TestWorkflowHealth` — smoke test for route registration

## Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Node registry replaces hardcoded nodeTypes/edgeTypes | ✅ |
| 2 | Mode switcher toggles Blueprint/Workflow | ✅ |
| 3 | Workflow nodes appear (inactive) in palette | ✅ |
| 4 | Control flow edges render with distinct styles | ✅ |
| 5 | WorkflowDefinition CRUD via API | ✅ |
| 6 | Compiler validates blueprint references | ✅ |
| 7 | Schema v2 migration with version tracking | ✅ |
| 8 | i18n keys for both EN and DE | ✅ |
| 9 | All Phase 3 tests still pass | ✅ |
| 10 | New Phase 4 tests pass | ✅ |
