# Blueprint System — backend

# Blueprint System — Backend Module

The Blueprint System provides the configuration layer for multi-agent debate workflows. It defines, persists, and validates all the building blocks — LLM profiles, role definitions, prompt templates, agent blueprints, canvas layouts, and workflow graphs — and supplies the tools to assemble them into compiled, executable workflows.

## Core Concepts

| Concept | Role |
|---|---|
| **BlueprintLLMProfile** | Provider/model configuration (OpenRouter, local, etc.) |
| **RoleType** | Predefined role categories with default settings |
| **RoleDefinition** | Concrete role instantiation (links to prompt, sets thresholds) |
| **PromptTemplate** | Prompt content with variant and language tags |
| **AgentBlueprint** | Complete agent recipe: LLM + role + optional prompt override |
| **CanvasLayout** | Visual spatial arrangement of workflow nodes |
| **WorkflowDefinition** | Executable workflow graph: nodes, edges, entry point, termination conditions |
| **BlueprintRepository** | SQLite-backed persistence for all the above |
| **BlueprintImporter** | YAML + Markdown filesystem importer (new and legacy formats) |
| **CanvasToWorkflowConverter** | Converts a visual canvas layout to a workflow definition |
| **CompilerService** | Validates a workflow definition and resolves all cross-references |

## Data Models

### Core Blueprint Entities (`backend/blueprints/models`)

**`BlueprintLLMProfile`** \
Represents an LLM endpoint configuration.

```python
profile = BlueprintLLMProfile(
    id="my-llm",
    name="My LLM",
    provider="openrouter",
    model="anthropic/claude-3.5-sonnet",
    api_key_env="OPENROUTER_API_KEY",
    temperature=0.7,
    max_tokens=4096,
)
```

- `id` must match the pattern `^[a-z][a-z0-9._-]*$`
- `temperature` clamped to [0.0, 2.0], `max_tokens` >= 1
- Supports providers: openrouter, openai, anthropic, local, ollama, opencode-zen, opencode-go, xiaomi
- Auto-generates `created_at` and `updated_at` timestamps
- Provides `from_legacy(LLMProfile)` and `to_legacy()` for interoperability with `backend.core.profiles`

**`PromptTemplate`** \
A prompt variant stored as inline text with a computed content hash.

```python
template = PromptTemplate(
    id="prompt-strategist",
    name="Strategist",
    role_type_id="strategist",   # or role="strategist"
    content="You are a strategist…",
    variant="default",           # defaults to "default"
    language="de",               # defaults to "de"
)
```

- `content` must not be blank
- `content_hash` auto-computed (16-char hex) unless explicitly provided
- `role` and `role_type_id` are aliases; `role_type_id` takes precedence

**`RoleType`** \
A category of role with default operational parameters.

```python
rt = RoleType(
    id="strategist",
    name="Strategist",
    description="Strategic analysis",
    icon="🧠",
    color="#8b5cf6",
    default_max_rounds=5,
    default_consensus_threshold=0.9,
    category="functional",         # "functional" or "formative"
    is_active=True,
)
```

- Seed data includes 8 role types: strategist, critic, optimizer, moderator, fact-checker, expert-reviewer, analyst, creative
- `category` defaults to `"functional"` for new roles (analyst, creative, fact-checker, expert-reviewer); moderator retains `"formative"`
- `consensus_threshold` validated to [0.0, 1.0], `max_rounds` >= 1
- `id` follows the same pattern as `BlueprintLLMProfile.id`

**`RoleDefinition`** \
A concrete role bound to a prompt template, with optional `argumentation_pattern` and `mode`.

```python
rd = RoleDefinition(
    id="role-strategist",
    name="Strategist",
    role_type_id="strategist",
    prompt_template_id="prompt-strategist",
    max_rounds=5,
    consensus_threshold=0.9,
    argumentation_pattern="kantian",   # optional
    mode="adversary",                  # optional
    tags=["default"],
)
```

- `from_legacy(AgentPersona)` and `to_legacy()` preserve the new `argumentation_pattern` and `mode` fields
- `mode` can be e.g. `"facilitator"`, `"adversary"`

**`AgentBlueprint`** \
The complete agent configuration. Binds an LLM profile to a role definition.

```python
bp = AgentBlueprint(
    id="bp-strategist",
    name="Strategist Blueprint",
    llm_profile_id="test-llm",
    role_definition_id="role-strategist",
    prompt_template_id="prompt-strategist-kantian",  # optional override
    is_active=True,
)
```

- `is_active` allows deactivating a blueprint without deleting it
- Supports `active_only` filtering in the repository

**`CanvasLayout`** \
Stores the visual arrangement of a workflow on the canvas.

```python
layout = CanvasLayout(
    id="layout-mvp",
    name="MVP Debate",
    project_id="proj-alpha",                    # optional grouping
    layout_data=CanvasLayoutData(
        nodes=[CanvasLayoutNode(id="n1", type="wf-strategist", x=100, y=200)],
        edges=[CanvasLayoutEdge(id="e1", source="n1", target="n2", type="uses_llm")],
        viewport=CanvasLayoutViewport(x=0, y=0, zoom=1),
    ),
)
```

- `CanvasLayoutNode` may carry `blueprint_id` and `agent_blueprint_id` — used by the converter to resolve which `AgentBlueprint` a workflow node references
- Node types include agent‑role nodes (`wf-strategist`, `wf-critic`, `wf-optimizer`, `wf-moderator`, `wf-fact-checker`, `wf-analyst`, `wf-creative`), support nodes (`wf-input`, `wf-gate`, `wf-user-injection`), and asset nodes (`agent-blueprint`, `llm-profile`)
- Edges carry a `type` distinguishing sequential, feedback, conditional, interjection, and `implements_role` (asset-to-workflow-node)

### Workflow Graph Models (`backend/blueprints/workflow_models`)

**`WorkflowNode`** \
A node in the executable workflow graph.

```python
node = WorkflowNode(
    id="n1",
    type="wf-strategist",
    label="Strategist",
    agent_blueprint_id="bp-1",   # required for agent types
    config={"max_rounds": 7},    # optional
    position={"x": 100, "y": 200},
)
```

- Agent node types (`wf-strategist`, `wf-critic`, `wf-optimizer`, `wf-moderator`, `wf-fact-checker`, `wf-analyst`, `wf-creative`) **must** have an `agent_blueprint_id`
- Non‑agent types (`wf-input`, `wf-initialize`, `wf-gate`, `wf-user-injection`) must **not** have one
- `config` is a free‑form dict; gates store `{"condition": "round >= 3"}`

**`WorkflowEdge`** \
A directed edge between two workflow nodes.

```python
edge = WorkflowEdge(
    source="n1",
    target="n2",
    type="sequential",            # sequential | conditional | feedback | interjection
    condition="round >= 3",      # required when type == "conditional"
)
```

- Auto‑generates a short ID if not provided
- `condition` is mandatory for `conditional` edges

**`TerminationCondition`** \
A condition that stops workflow execution.

```python
tc = TerminationCondition(
    type="max_rounds",        # max_rounds | consensus_reached | time_limit | custom
    value=5,
    description="Optional description",
)
```

**`WorkflowDefinition`** \
The complete workflow graph. Supersedes the legacy `execution_order` + `node_blueprint_map` approach.

```python
wf = WorkflowDefinition(
    name="My Workflow",
    nodes=[...],
    edges=[...],
    entry_point="input-1",
    termination_conditions=[TerminationCondition(type="max_rounds", value=3)],
    version=2,
    is_locked=True,
)
```

- `entry_point` must reference a node ID present in `nodes`
- Legacy fields `execution_order` and `node_blueprint_map` are still populated for backward compatibility by the converter and compiler
- `version` defaults to 1, `is_locked` to False
- Also stores `conditional_edges` and `interjection_points` for backward compat

**`ConditionalEdge`** (legacy, still supported) \
```python
ConditionalEdge(source_node_id="n1", target_node_id="n2", condition="consensus_reached")
```

**`InterjectionPoint`** (legacy, still supported) \
```python
InterjectionPoint(node_id="n1", input_type="user_query", blocking=True)
```

## BlueprintRepository

The repository (`backend/blueprints/repository.py`) provides CRUD operations for all blueprint entities. It uses SQLite via a connection managed by the repository instance.

```python
repo = BlueprintRepository(db_path="/path/to/blueprints.db")
```

### Methods per entity

| Entity | Save | Get | List | Delete |
|---|---|---|---|---|
| `BlueprintLLMProfile` | `save_llm_profile` | `get_llm_profile(id)` | `list_llm_profiles()` | `delete_llm_profile(id)` |
| `PromptTemplate` | `save_prompt_template` | `get_prompt_template(id)` | `list_prompt_templates(role, variant)` | `delete_prompt_template(id)` |
| `RoleDefinition` | `save_role_definition` | `get_role_definition(id)` | `list_role_definitions(role)` | `delete_role_definition(id)` |
| `RoleType` | `save_role_type` | `get_role_type(id)` | `list_role_types(active_only)` | `delete_role_type(id)` |
| `AgentBlueprint` | `save_blueprint` | `get_blueprint(id)` | `list_blueprints(active_only)` | `delete_blueprint(id)` |
| `CanvasLayout` | `save_layout` | `get_layout(id)` | `list_layouts(project_id)` | `delete_layout(id)` |
| `WorkflowDefinition` | `save_workflow_definition` | `get_workflow_definition(id)` | `list_workflow_definitions(limit, offset)` | `delete_workflow_definition(id)` |

- All save operations are upserts (insert or update)
- Foreign key constraints are enforced at the database level (e.g., `AgentBlueprint.llm_profile_id` must reference an existing profile)
- Workflow definitions serialize `WorkflowNode`, `WorkflowEdge`, and `TerminationCondition` lists as JSON columns

## BlueprintImporter

The importer (`backend/blueprints/importer.py`) reads blueprint definitions from the filesystem and persists them idempotently.

```python
importer = BlueprintImporter(
    repo=repo,
    profile_dir=Path("profiles"),
    archive_dir=Path("archive/config"),
)
result = importer.import_all(dry_run=False)
```

### Import capabilities

- **New‑format LLM profiles**: Reads YAML files from `profiles/llm/*.yaml`
- **Legacy LLM profiles**: Reads `archive/config/llm_profiles.yaml` (pre‑blueprint format) and tags them with `"legacy-import"`
- **Agent personas**: Reads YAML files from `profiles/agents/*.yaml`, creates `RoleDefinition` instances. The `system_prompt` field is intentionally dropped (stored separately as a prompt template)
- **Prompt templates**: Reads `.md` files from `profiles/prompts/{variant}/*.md`. The variant directory name becomes the `variant` field (e.g., `default`, `kantian`, `dialectic`). Archive prompts get variant `"archive"`
- **Argumentation patterns**: Located under `profiles/argumentation-patterns/{pattern}/*.md`; loaded via `PromptService` rather than the importer

### Import result

`BlueprintImporter.import_all()` returns an `ImportResult` with:

| Field | Description |
|---|---|
| `created` | Number of new entities persisted |
| `updated` | Number of existing entities modified (content hash changed) |
| `skipped` | Number of unchanged entities |
| `errors` | List of error messages |
| `total` | `created + updated + skipped` |

### Key behaviors

- **Idempotency**: Running import twice yields `created=0, skipped=N` on the second run, provided no files changed
- **Dry run**: `import_all(dry_run=True) ` reports what *would* happen without touching the database
- **No auto‑assembly**: Import does **not** create `AgentBlueprint` instances — users do that in a later step (Phase 3)
- **Change detection**: Uses content hashes to detect updated prompt files

## Canvas-to-Workflow Conversion

`CanvasToWorkflowConverter` (`backend/blueprints/canvas_to_workflow.py`) transforms a visual `CanvasLayout` into a `WorkflowDefinition`.

```python
converter = CanvasToWorkflowConverter(repo)
wf = converter.convert(
    layout,
    name="My Workflow",      # defaults to layout.name
    description="...",
)
```

### Conversion rules

1. **Node resolution**: Only nodes of type `wf-*` are included; asset nodes (`agent-blueprint`, `llm-profile`) are excluded
2. **Blueprint mapping**: If a workflow node has `agent_blueprint_id` in its `data`, that value is used. Otherwise the converter looks for an incoming edge of type `implements_role` from an asset node with a `blueprint_id`
3. **Edge filtering**: Only edges between workflow nodes are kept in the workflow; asset‑related edges (`implements_role`) are excluded but their data informs blueprint resolution
4. **Entry point**: The `wf-input` node is preferred. If absent, the node with no incoming edges becomes the entry point
5. **Termination conditions**: Extracted from a `wf-moderator` node’s `config` (keys `max_rounds`, `consensus_threshold`) if present; otherwise default values are used
6. **Backward compatibility**: Populates `execution_order` and `node_blueprint_map` from the resolved nodes

### Errors

- `ConversionError` raised when there are **no workflow nodes** in the canvas

## Workflow Compilation

`CompilerService` (`backend/blueprints/compiler.py`) validates a `WorkflowDefinition` and resolves all references into a `CompilationResult`.

```python
compiler = CompilerService(repo)
result = compiler.compile(wf)
```

### Compilation result

| Field | Type | Description |
|---|---|---|
| `is_valid` | `bool` | True if all checks pass |
| `resolved_agents` | `list[ResolvedAgentConfig]` | Fully resolved agent configurations |
| `errors` | `list[str]` | Validation errors |
| `warnings` | `list[str]` | Non‑blocking warnings |
| `node_sequence` | `list[str]` | Topologically sorted node IDs |

Each `ResolvedAgentConfig` includes:

- `role` (from `RoleDefinition.role_type_id`)
- `llm_model` (from the linked `BlueprintLLMProfile.model`)
- `llm_profile_id`
- `prompt_content` (from the linked prompt template)
- `argumentation_pattern`
- `mode`
- `max_rounds`, `consensus_threshold`

### Validation checks

- Every `agent_blueprint_id` references an existing `AgentBlueprint` in the repo
- The referenced blueprint’s `llm_profile_id` and `role_definition_id` exist and are resolvable
- `execution_order` and `conditional_edges` node IDs are present in `node_blueprint_map`
- `interjection_points` node IDs exist
- Gate nodes must have exactly two outgoing edges (when present in graph mode)
- No cycles (feedback edges are allowed and don’t count as cycles)
- Inactive blueprints produce a warning but do not block compilation
- An empty workflow (no nodes) is valid

## Factory Functions

### `build_mvp_debate_workflow`

Creates a standard four‑role debate workflow (strategist → critic → optimizer → moderator) with a feedback edge from moderator back to strategist.

```python
from backend.blueprints.mvp_debate_canvas import build_mvp_debate_workflow

wf = build_mvp_debate_workflow(
    repo,
    llm_profile_ids={
        "strategist": "llm-strategist",
        "critic": "llm-critic",
        "optimizer": "llm-optimizer",
        "moderator": "llm-moderator",
    },
    max_rounds=5,
    consensus_threshold=0.85,
    name="Custom Debate",
    description="...",
)
```

- If `llm_profile_ids` is omitted, the first available LLM profile in the repository is used for all four agents
- Creates `AgentBlueprint` instances idempotently using fixed IDs (`mvp-strategist`, etc.)
- Termination conditions are set from parameters
- Raises `ValueError` if a referenced LLM profile does not exist or if no LLM profiles exist

## Migration System

The module runs schema migrations automatically on repository creation via `run_migrations(db_path)`. The current schema version is tracked using the `SCHEMA_VERSION` constant.

```python
from backend.blueprints.migrations import run_migrations, SCHEMA_VERSION

run_migrations(db_path)   # safe to call multiple times
assert SCHEMA_VERSION == 14  # example, varies
```

Notable migrations:

- v4: Added `nodes_json`, `edges_json`, `entry_point`, `termination_conditions_json`, `version`, `is_locked` columns to `workflow_definitions`
- v14: Seed data for 8 role types (including analyst, creative, fact‑checker, expert‑reviewer)

## Integration with the Rest of the Codebase

```mermaid
flowchart LR
    subgraph Blueprint System
        A[BlueprintImporter] -->|Import YAML/MD| B[BlueprintRepository]
        C[Canvas Layout] --> D[CanvasToWorkflowConverter]
        B -->|CRUD| E[Factory Functions]
        D --> F[WorkflowDefinition]
        E --> F
        F --> G[CompilerService]
        B -->|Lookup| G
    end

    subgraph Downstream
        G -->|Compiled Workflow| H[WorkflowCompiler\n(backend/workflow)]
        H --> I[LangGraph Execution]
    end

    subgraph Upstream
        J[AgentPersona\n(backend/core/profiles)] -.->|Legacy compat| A
        K[PromptService\n(backend/services)] -.->|Prompt assembly| G
    end
```

- **`backend.core.profiles`**: Provides `LLMProfile` and `AgentPersona` for legacy conversion (`from_legacy` / `to_legacy`). The `AgentPersona.role` field has been widened to accept new role types (analyst, creative, etc.)
- **`backend.workflow.workflow_compiler`**: The `WorkflowCompiler` takes a `WorkflowDefinition` and produces a LangGraph executable graph. Used in the MVP debate end‑to‑end flow
- **`backend.services.prompt_service`**: `PromptService` loads argumentation patterns and workflow variants from the filesystem and assembles final prompts by combining pattern content with the workflow variant. Used during compilation to resolve prompt content
- **`backend.services.tone_prompt_injector`**: Injects tone profiles (e.g., academic, socratic) into compiled prompts at runtime (not part of the blueprint system directly but called after compilation)