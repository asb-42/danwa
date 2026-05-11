# Canvas-based RoleType → RoleDefinition → AgentPersona Assignment

## Problem

Currently, Agent Personas have a hardcoded `role` field (strategist/critic/optimizer/moderator) set via a dropdown in the Config UI. This creates two limitations:

1. **No multi-role**: A persona can only be one role. To use the same persona as both "critic" and "fact-checker", you need duplicate entries.
2. **No visual composition**: Role assignment is invisible — you can't see which personas serve which roles in a workflow.

## Current State

The Blueprint Canvas already has the infrastructure:

| Component | Exists? | Status |
|-----------|---------|--------|
| `RoleType` node | ✅ | Registered in registry, renders on canvas |
| `RoleDefinition` node | ✅ | Registered in registry, renders on canvas |
| `AgentBlueprint` node | ✅ | Composite: LLM + Role + Prompt |
| `defines_role` edge | ✅ | RoleType → RoleDefinition |
| `implements_role` edge | ✅ | RoleDefinition → AgentBlueprint |
| `uses_llm` edge | ✅ | AgentBlueprint → LLMProfile |
| `prompted_by` edge | ✅ | AgentBlueprint → PromptTemplate |

**What's missing**: The edges are visual only — they don't update the backend models when connected.

## Target Architecture

```
┌──────────┐  defines_role   ┌─────────────────┐  implements_role  ┌──────────────────┐
│ RoleType │ ─────────────→  │ RoleDefinition   │ ───────────────→ │ AgentBlueprint   │
│ (🧠 Critic)│                │ (critic-persona) │                  │ (claude-critic)  │
└──────────┘                 │ role_type_id: ───│                  │ role_def_id: ────│
                             │  "critic"        │                  │  "critic-persona"│
                             └─────────────────┘                  └────────┬─────────┘
                                                                          │ uses_llm
                                                                          │ prompted_by
                                                             ┌────────────┴──────────┐
                                                             ▼                       ▼
                                                       ┌──────────┐          ┌──────────────┐
                                                       │LLMProfile│          │PromptTemplate│
                                                       └──────────┘          └──────────────┘
```

## Changes

### Phase 1: Edge → Backend Wiring (Core) ✅ DONE

**Goal**: When edges are connected/disconnected on the canvas, update the backend models.

#### 1.1 `defines_role` edge → update `RoleDefinition.role_type_id` ✅

- **Frontend**: [`edgeWiring.js`](frontend/src/lib/blueprint/edgeWiring.js) — on connect, calls `updateRoleDefinition(role_def_id, { role_type_id: role_type_id })`
- **Frontend**: On disconnect, calls `updateRoleDefinition(role_def_id, { role_type_id: 'strategist' })` (default fallback)
- **Backend**: [`RoleDefinition.role_type_id`](backend/blueprints/models.py:214) already exists — no model change needed

#### 1.2 `implements_role` edge → update `AgentBlueprint.role_definition_id` ✅

- **Frontend**: [`edgeWiring.js`](frontend/src/lib/blueprint/edgeWiring.js) — on connect, calls `updateAgentBlueprint(blueprint_id, { role_definition_id: role_def_id })`
- **Frontend**: On disconnect, calls `updateAgentBlueprint(blueprint_id, { role_definition_id: '' })`
- **Backend**: [`AgentBlueprint.role_definition_id`](backend/blueprints/models.py:344) already exists — no model change needed

#### 1.3 `uses_llm` edge → update `AgentBlueprint.llm_profile_id` ✅

- **Frontend**: [`edgeWiring.js`](frontend/src/lib/blueprint/edgeWiring.js) — on connect, calls `updateAgentBlueprint(blueprint_id, { llm_profile_id: profile_id })`

#### 1.4 `prompted_by` edge → update `RoleDefinition.prompt_template_id` ✅

- **Frontend**: [`edgeWiring.js`](frontend/src/lib/blueprint/edgeWiring.js) — on connect, calls `updateRoleDefinition(role_def_id, { prompt_template_id: template_id })`

#### 1.5 `overrides_prompt` edge → update `AgentBlueprint.prompt_template_id` ✅

- **Frontend**: [`edgeWiring.js`](frontend/src/lib/blueprint/edgeWiring.js) — on connect, calls `updateAgentBlueprint(blueprint_id, { prompt_template_id: template_id })`

### Phase 2: Inspector Panel Enhancements ✅ DONE

**Goal**: When a node is selected, show its connections and allow editing.

#### 2.1 RoleType Inspector ✅

- Show connected RoleDefinitions (from `defines_role` edges)
- Show behavioral defaults (max_rounds, consensus_threshold)
- Inline edit: name, icon, color, defaults

#### 2.2 RoleDefinition Inspector ✅

- Show connected RoleType (from `defines_role` edge)
- Show connected AgentBlueprints (from `implements_role` edges)
- Show prompt template reference
- Inline edit: name, description, prompt_template_id
- **Bugfix**: Fixed undefined `roles` variable — now uses `roleTypes` from API

#### 2.3 AgentBlueprint Inspector ✅

- Show all connections: LLM, Role, Prompt
- Show computed properties: effective config summary (LLM, Role, Prompt)
- Inline edit: name, description, tags

### Phase 3: Canvas → Workflow Compilation ✅ DONE

**Goal**: When a WorkflowDefinition is compiled, resolve the full RoleType chain.

#### 3.1 Compiler Enhancement ✅

- [`compiler.py`](backend/blueprints/compiler.py:27): `ResolvedAgent` dataclass extended with RoleType metadata: `role_type_name`, `role_type_icon`, `role_type_color`, `default_max_rounds`, `default_consensus_threshold`
- [`compiler.py`](backend/blueprints/compiler.py:133): Legacy `compile()` now resolves `RoleType` from `RoleDefinition.role_type_id` via `repo.get_role_type()`
- [`workflow_compiler.py`](backend/workflow/workflow_compiler.py:43): `ResolvedAgentConfig` extended with same RoleType fields
- [`workflow_compiler.py`](backend/workflow/workflow_compiler.py:160): `_resolve_agent_config()` resolves RoleType chain with fallback warning
- [`workflow_compiler.py`](backend/workflow/workflow_compiler.py:412): Moderator node uses `default_consensus_threshold` from RoleType instead of hardcoded 0.7

#### 3.2 Runtime Integration ✅

- [`node_functions.py`](backend/workflow/node_functions.py:718): `_resolve_system_prompt()` enhanced to use RoleType name/icon for custom role type fallback prompts

### Phase 4: Config UI Fallback ✅ DONE

**Goal**: Show which agent personas are managed by Blueprint Canvas.

- [`ConfigView.svelte`](frontend/src/views/ConfigView.svelte:155): `refreshLists()` now loads `listRoleDefinitions()` to build `blueprintRoleDefIds` set
- [`ConfigView.svelte`](frontend/src/views/ConfigView.svelte:162): `isBlueprintManaged()` checks if a persona ID exists in the blueprint role definitions
- [`ConfigView.svelte`](frontend/src/views/ConfigView.svelte:599): Agent persona cards show a 🧩 badge with "Managed by Blueprint Canvas" tooltip for blueprint-managed personas
- i18n: Added `config.managedByBlueprint` key in DE + EN

## Data Model (No Changes Needed)

All models already support the required relationships:

```
RoleType.id ←── RoleDefinition.role_type_id
RoleDefinition.id ←── AgentBlueprint.role_definition_id
BlueprintLLMProfile.id ←── AgentBlueprint.llm_profile_id
PromptTemplate.id ←── AgentBlueprint.prompt_template_id
```

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Edge disconnected | Set FK to null, log warning |
| RoleType deleted | Cascade: null role_type_id on RoleDefinitions |
| RoleDefinition deleted | Cascade: null role_definition_id on AgentBlueprints |
| Multiple RoleTypes → one RoleDefinition | Last write wins (UI prevents via validation) |
| Canvas edge + Config UI edit | Canvas takes precedence (DB is SSOT) |

## Implementation Order

1. **Phase 1**: Edge → Backend wiring (5 edge types) ✅ DONE
2. **Phase 2**: Inspector enhancements (3 node types) ✅ DONE
3. **Phase 3**: Compiler resolution ✅ DONE
4. **Phase 4**: Config UI fallback badges ✅ DONE

## Scope: What Changes, What Doesn't

| Component | Change? | Notes |
|-----------|---------|-------|
| Edge components (4) | **YES** | Add onConnect/onDisconnect handlers |
| BlueprintCanvas.svelte | **YES** | Wire edge events to API calls |
| Inspector.svelte | **YES** | Show connected nodes, inline edit |
| Compiler service | **YES** | Resolve RoleType chain at compile time |
| Backend models | NO | All relationships already exist |
| Backend API | NO | CRUD endpoints already exist |
| Config UI | NO | Fallback remains as-is |
| Workflow runtime | NO | Already reads from ProfileService |

## Risks

- **Edge event timing**: Svelte Flow fires `onConnect` before the edge is rendered. Need to ensure API call completes before updating local state.
- **Circular dependencies**: RoleType → RoleDefinition → AgentBlueprint → RoleType (shouldn't happen, but need validation).
- **Performance**: Each edge connection triggers an API call. Batch updates for drag-and-drop reconnections.
