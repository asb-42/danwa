# Blueprint Canvas — Phase 3: Frontend Canvas UI

## 1. Overview

Phase 3 implements the interactive three-column Blueprint Canvas editor using Svelte Flow (`@xyflow/svelte`). Users can visually model Agent Blueprints by dragging entity types from a Palette onto a canvas, connecting them with semantic edges, and editing properties in an Inspector panel.

### Goals

- Three-column layout: Palette (240px) | Canvas (flex) | Inspector (320px)
- 4 custom node types: AgentBlueprint, LLMProfile, RoleDefinition, PromptTemplate
- 4 semantic edge types: uses_llm, implements_role, prompted_by, overrides_prompt
- Drag & drop from palette to canvas
- Connection validation (only valid edges allowed)
- Context-sensitive Inspector forms for each entity type
- Canvas layout persistence (save/load/delete)
- ELK.js auto-layout
- Import existing YAML/MD configs
- Full i18n support (EN + DE, ~40 keys each)

## 2. Architecture

### 2.1 State Management

A class-based rune store (`BlueprintCanvasStore`) using Svelte 5 `$state` runes manages all canvas state:

- `nodes` / `edges` — Svelte Flow node/edge arrays
- `selectedNodeId` — currently selected node for Inspector
- `currentLayoutId` — ID of the loaded layout (null for new)
- `isDirty` — tracks unsaved changes

Exported as a singleton: `canvasStore`.

### 2.2 File Structure

```
frontend/src/
├── lib/blueprint/
│   ├── store.svelte.js    # BlueprintCanvasStore (runes)
│   ├── api.js             # API client functions
│   ├── validation.js      # Edge connection validation
│   ├── dnd.js             # Drag & Drop utilities
│   └── layout.js          # ELK auto-layout
├── components/blueprint/
│   ├── Palette.svelte     # Draggable palette + saved layouts
│   ├── BlueprintCanvas.svelte  # SvelteFlow canvas + toolbar
│   ├── Inspector.svelte   # Context-sensitive form router
│   ├── nodes/
│   │   ├── AgentBlueprintNode.svelte
│   │   ├── LLMProfileNode.svelte
│   │   ├── RoleDefinitionNode.svelte
│   │   └── PromptTemplateNode.svelte
│   ├── edges/
│   │   ├── UsesLlmEdge.svelte        (blue solid)
│   │   ├── ImplementsRoleEdge.svelte  (violet solid)
│   │   ├── PromptedByEdge.svelte      (emerald dashed)
│   │   └── OverridesPromptEdge.svelte (amber dotted)
│   └── forms/
│       ├── AgentBlueprintForm.svelte
│       ├── LLMProfileForm.svelte
│       ├── RoleDefinitionForm.svelte
│       └── PromptTemplateForm.svelte
└── views/
    └── BlueprintCanvasView.svelte  # Top-level view
```

### 2.3 Routing

The Blueprint Canvas is accessible at `#/blueprint` via hash-based routing in [`App.svelte`](../frontend/src/App.svelte).

### 2.4 Navigation

A "🧩 Blueprint Canvas" entry was added to the sidebar nav in [`Sidebar.svelte`](../frontend/src/components/Sidebar.svelte), positioned after "Debate".

## 3. Custom Nodes

### 3.1 AgentBlueprintNode

- Displays: name, ascendency badge (kantian=violet, hegelian=amber, steiner=emerald)
- Linked indicators: ✓/○ for LLM, Role, Prompt connections
- Handles: LEFT (target), RIGHT (source)
- Border: gray-400

### 3.2 LLMProfileNode

- Displays: name, provider icon (🌐 openrouter, 🟢 openai, 🟠 anthropic, 💻 local, 🦙 ollama), model name
- A2A badge if `a2a_endpoint` is set
- Border: blue (#3b82f6)

### 3.3 RoleDefinitionNode

- Displays: name, role icon (🧠 strategist, 🔍 critic, ⚡ optimizer, 🎯 moderator), ascendency badge
- Tag count display
- Border: violet (#8b5cf6)

### 3.4 PromptTemplateNode

- Displays: name, 3-line content preview (first 3 non-empty lines, truncated to 40 chars)
- Variable count display
- Border: emerald (#10b981)

## 4. Semantic Edges

| Edge Type | Color | Style | Source → Target |
|-----------|-------|-------|-----------------|
| `uses_llm` | Blue #3b82f6 | Solid | AgentBlueprint → LLMProfile |
| `implements_role` | Violet #8b5cf6 | Solid | AgentBlueprint → RoleDefinition |
| `prompted_by` | Emerald #10b981 | Dashed (8 4) | AgentBlueprint → PromptTemplate |
| `overrides_prompt` | Amber #f59e0b | Dotted (4 4) | RoleDefinition → PromptTemplate |

## 5. Connection Validation

Only valid connections are allowed:

```
AgentBlueprint → LLMProfile        (uses_llm)
AgentBlueprint → RoleDefinition     (implements_role)
AgentBlueprint → PromptTemplate     (prompted_by)
RoleDefinition → PromptTemplate     (overrides_prompt)
```

Invalid connections are rejected with a visual indicator.

## 6. Drag & Drop

- Palette items use HTML5 Drag API with custom MIME type `application/blueprint-node-type`
- `screenToFlowPosition()` converts screen coordinates to flow coordinates accounting for viewport transform
- `createDraftNode()` generates nodes with `draft-{uuid}` IDs
- Drop zone on canvas creates new nodes at drop position

## 7. Inspector Forms

Each node type has a dedicated form component:

- **AgentBlueprintForm**: name, description, llm_profile_id (select), role_definition_id (select), prompt_template_id (select). Dropdowns populated from API.
- **LLMProfileForm**: name, provider (select), model, temperature, max_tokens
- **RoleDefinitionForm**: name, role (select), description, prompt_template_id (select), consensus_threshold, max_rounds
- **PromptTemplateForm**: name, role (select), variant, language (select), content (textarea, monospace)

Forms use POST for draft nodes, PUT for existing entities.

## 8. Canvas Persistence

Layouts are saved via the Canvas Layout API (`/api/v1/canvas/layouts`):

- **Save**: Serializes nodes (id, type, position, blueprint_id) and edges (id, source, target, type) to JSON
- **Load**: Fetches layout + entity data for each node, restores canvas state
- **Delete**: Removes saved layout from server

## 9. Auto-Layout

ELK.js with layered algorithm (RIGHT direction) provides automatic node positioning:

| Node Type | Width | Height |
|-----------|-------|--------|
| agent-blueprint | 220 | 120 |
| llm-profile | 200 | 100 |
| role-definition | 200 | 100 |
| prompt-template | 200 | 110 |

## 10. i18n

~40 translation keys per language under the `blueprint.*` namespace:

- `nav.blueprint` — Sidebar label
- `blueprint.palette.*` — Palette items and labels
- `blueprint.canvas.*` — Canvas toolbar and dialogs
- `blueprint.inspector.*` — Inspector panel
- `blueprint.form.*` — Form field labels
- `blueprint.node.*` / `blueprint.edge.*` — Node/edge labels
- `blueprint.toast.*` — Success/error messages

## 11. API Endpoints Used

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET/POST/PUT/DELETE | `/api/v1/blueprints/llm-profiles` | LLM Profile CRUD |
| GET/POST/PUT/DELETE | `/api/v1/blueprints/prompt-templates` | Prompt Template CRUD |
| GET/POST/PUT/DELETE | `/api/v1/blueprints/role-definitions` | Role Definition CRUD |
| GET/POST/PUT/DELETE | `/api/v1/blueprints/agent-blueprints` | Agent Blueprint CRUD |
| GET/POST/PUT/DELETE | `/api/v1/canvas/layouts` | Canvas Layout CRUD |
| POST | `/api/v1/blueprints/import` | Import YAML/MD configs |

## 12. Implementation Order

1. Library modules (store, api, validation, dnd, layout)
2. Custom nodes (4 components)
3. Custom edges (4 components)
4. Main components (Palette, Canvas, Inspector, Forms)
5. View component (BlueprintCanvasView)
6. Integration (route, sidebar, i18n, proxy, docs)

## 13. Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| AC-3.1 | Three-column layout renders correctly | ✅ |
| AC-3.2 | 4 palette items are draggable | ✅ |
| AC-3.3 | Nodes created on drop with correct type | ✅ |
| AC-3.4 | Only valid connections accepted | ✅ |
| AC-3.5 | Semantic edges render with correct colors/styles | ✅ |
| AC-3.6 | Inspector shows correct form per node type | ✅ |
| AC-3.7 | Forms create/update entities via API | ✅ |
| AC-3.8 | Layout save/load/delete works | ✅ |
| AC-3.9 | Auto-layout repositions nodes | ✅ |
| AC-3.10 | Import button triggers config import | ✅ |
| AC-3.11 | i18n works for EN and DE | ✅ |
| AC-3.12 | Route `#/blueprint` accessible | ✅ |
| AC-3.13 | Sidebar nav item present | ✅ |
