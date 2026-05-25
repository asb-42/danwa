# Blueprint System — blueprints

# Blueprint Canvas — Data Layer (`backend/blueprints`)

The `blueprints` package is the canonical data layer for the Blueprint Canvas feature. It provides domain models, persistence, import/export, canvas-to-workflow conversion, and compilation validation — all the infrastructure needed to define, store, and transform agent workflows.

---

## Overview

```
┌──────────────────────────────────────────────────────────────┐
│                      Blueprint Canvas                        │
│                                                              │
│  ┌─────────────────┐   ┌───────────────┐   ┌──────────┐     │
│  │  BlueprintRepo   │   │  CanvasLayout │   │ Workflow │     │
│  │  (persistence)   │◄──│  (visual)     │──►│Definitn. │     │
│  └────────┬────────┘   └───────┬───────┘   └────┬─────┘     │
│           │                    │                 │           │
│  ┌────────┴────────┐   ┌───────┴───────┐   ┌────┴─────┐     │
│  │  Importer        │   │ CanvasToWF    │   │ Compiler |     │
│  │  (YAML/MD→DB)    │   │ (layout→wf)   │   │(validate)│     │
│  └─────────────────┘   └───────────────┘   └──────────┘     │
│                                                              │
│  ┌─────────────────┐   ┌───────────────┐                    │
│  │  BundleComposer  │   │  BundleIO     │                    │
│  │  (modular comp.) │──►│ (export/imp.) │                    │
│  └─────────────────┘   └───────────────┘                    │
└──────────────────────────────────────────────────────────────┘
```

The package is the single source of truth for:
- **Domain models** – Pydantic v2 models for agents, LLM profiles, roles, prompts, tone, canvas layouts, workflow definitions, and bundles.
- **SQLite persistence** – A `BlueprintRepository` that wraps the database and provides CRUD for all entity types.
- **Idempotent import** – YAML/MD → database migration for existing configuration files.
- **Bundle architecture** – Portable, composable unit (AgentBundle) that aggregates an LLM profile, role type, tone, and optional prompts/role definitions.
- **Canvas → Workflow conversion** – Translates a visual CanvasLayout into an executable WorkflowDefinition.
- **Workflow compilation** – Validates blueprint references and optionally generates a LangGraph StateGraph.

---

## Domain Models

All models are defined in `backend/blueprints/models.py` and `backend/blueprints/workflow_models.py` and re‑exported through `__init__.py`.

| Model | Purpose |
|---|---|
| `BlueprintLLMProfile` | LLM configuration (provider, model, temperature, A2A settings, …) |
| `RoleType` | Categorisation of roles (Strategist, Critic, Moderator, …) with defaults |
| `RoleDefinition` | Concrete role instance with argumentation pattern, mode, and linked prompt |
| `PromptTemplate` | A text prompt (role, variant, language, content hash) |
| `ToneProfile` | Stylistic configuration (formality, verbosity, emotional valence) |
| `AgentBlueprint` | Legacy aggregate: LLM profile + role definition + prompt |
| `CanvasLayout` | Visual node/edge positions and references (layout data) |
| `WorkflowDefinition` | Executable graph: nodes, edges, entry point, termination conditions |
| `WorkflowTemplate` | Reusable workflow template with placeholders |
| `AgentBundle` | Modern aggregate: composition of components + LLM + role type + tone |
| `BundleComposition` | Sub‑model inside `AgentBundle` storing module ID references (agent core, argumentation pattern, prompt modifier) |

All models use `datetime(UTC)` timestamps and store tags as JSON strings via `tags_json`.

---

## Persistence Layer

`BlueprintRepository` (in `backend/blueprints/repository.py`) is the single entry point for all database operations. It uses the SQLite schema created by `migrations.run_migrations()` and exposes methods like:

- `save_*` / `get_*` / `list_*` / `delete_*` for every entity
- `search_*` with filters (active, tags, name)
- Transactional bulk operations (e.g. for bundle import)

The repository is injected into every service class (`ComposerService`, `CompilerService`, `BundleComposer`, `CanvasToWorkflowConverter`, `BlueprintImporter`) following the repository pattern.

---

## Data Import (`importer.py`)

`BlueprintImporter` reads existing YAML configuration files and Markdown prompt files and writes them into the database idempotently.

```
import_all()
  ├── import_llm_profiles()
  │     ├── profiles/llm/*.yaml (new flat format)
  │     └── archive/config/llm_profiles.yaml (legacy nested format)
  ├── import_agent_personas()
  │     └── profiles/agents/*.yaml → RoleDefinition
  └── import_prompt_templates()
        ├── profiles/prompts/**/*.md
        └── archive/config/prompts/*.md
```

Key behaviours:
- **Idempotent** – compares content hashes (prompts) or field equality (profiles/roles) to skip unchanged records.
- **Dry‑run mode** – pass `dry_run=True` to see what would be created/updated without modifying the database.
- **Legacy conversion** – the private method `_convert_legacy_llm_profile` handles the old nested YAML format, inferring provider from model name or base URL via `_infer_provider`.

---

## Bundle System

### Bundle IO (`bundle_io.py`)

Portable serialisation of `AgentBundle` instances.

- **Export** – `export_bundle(bundle_id, repo)` resolves all referenced entities (LLM profile, role type, role definition, prompt template, tone profile) and returns a self‑contained JSON dict.
  `export_bundle_with_dependencies` optionally includes all role types.
- **Import** – `import_bundle(data, repo, conflict_strategy)` reconstructs entities in the database, resolving ID conflicts according to `ImportConflictStrategy` (`skip`, `overwrite`, `rename`). The import order is: role type → LLM profile → role definition → prompt template → tone profile → bundle entity. A `id_map` tracks remapped IDs when renaming.

### Bundle Composer (`composer.py`)

High‑level API for composing AgentBundles from modular components. Three paths exist in the system:

| Path | When used |
|---|---|
| **BundleResolver** (legacy) | role_type + role_definition + prompt_template |
| **PromptService** (fallback) | argumentation pattern + workflow variant |
| **BundleComposer** (new) | agent_core + argumentation_pattern + tone_profile + prompt_modifier + llm_profile |

`BundleComposer` implements Path C for the Builder UI.

```python
composer = BundleComposer(repo)

# List available components
components = composer.list_components()

# Preview the assembled system prompt (without saving)
prompt = composer.preview(composition)

# Create a bundle
bundle = composer.create(
    "My Agent",
    composition=Composition(
        agent_core_id="strategist-default",
        argumentation_pattern_id="kantian",
        tone_profile_id="formal",
        prompt_modifier_id="short-form",
    ),
    llm_profile_id="llm-claude-sonnet",
)

# Update existing bundle
composer.update(bundle.id, name="New Name", composition=new_comp)

# Export to JSON or filesystem
data = composer.export(bundle.id)
path = composer.export_to_directory(bundle.id)

# Import from filesystem
composer.import_from_directory(module_id)
```

The `BundleComposition` sub‑model stores **only module ID references** – at resolve time, `ComposerService.compose()` loads content from the module filesystem. This avoids duplicating inline content in the database.

---

## Canvas → Workflow Conversion (`canvas_to_workflow.py`)

`CanvasToWorkflowConverter` transforms a `CanvasLayout` (positions + entity references) into a `WorkflowDefinition` that the workflow engine can execute.

```python
converter = CanvasToWorkflowConverter(repo)
wf = converter.convert(
    layout,
    name="My Workflow",
    description="…",
    max_rounds=5,
    consensus_threshold=0.9,
)
```

Conversion steps:
1. **Filter nodes** – workflow nodes (type in `CANVAS_TO_WF_NODE_TYPE`) are kept; asset nodes (agent‑blueprint, LLM profile, …) are used only for ID resolution.
2. **Convert nodes** – each canvas node becomes a `WorkflowNode`. Agent blueprint IDs are resolved from connected asset nodes via edges.
3. **Convert edges** – canvas edges become `WorkflowEdge` objects; only those where both source and target are workflow nodes are included.
4. **Detect entry point** – prefers explicit `wf-input` node, then node with no incoming edges, then first node.
5. **Build termination conditions** – reads `max_rounds` and `consensus_threshold` from `wf-moderator` node config, falling back to parameters.
6. **Validate** – raises `ConversionError` if the canvas has no workflow nodes.

---

## Compilation and Validation (`compiler.py`)

`CompilerService` validates a `WorkflowDefinition` against the blueprint catalog and optionally produces a compiled LangGraph graph.

### CompilationResult

```python
@dataclass
class CompilationResult:
    is_valid: bool
    resolved_agents: list[ResolvedAgent]
    errors: list[str]
    warnings: list[str]
```

### `compile(workflow)` – Validation

Performs two sets of checks:

**Legacy (node_blueprint_map based):**  
- All referenced AgentBlueprints exist and are active.  
- Linked LLM profiles, role definitions, and role types exist.  
- `execution_order`, `conditional_edges`, and `interjection_points` reference valid node IDs.

**Graph (nodes/edges based):**  
- `entry_point` references an existing node.  
- Agent nodes have a valid `agent_blueprint_id`.  
- Gate nodes have ≥2 outgoing edges.  
- No isolated nodes.  
- Cycle detection (warning only – feedback edges create intentional cycles).  
- Edge source/target refer to existing nodes.  
- Tone profile edges follow constraints (source must be `wf-tone-profile`, target must be an agent node, at most one per agent, no isolation).

### `compile_to_langgraph(workflow)` – LangGraph

Delegates to `WorkflowCompiler` (in `backend/workflow/workflow_compiler.py`). It reuses the validation from `compile`, then constructs a `StateGraph` by:
- Topologically sorting nodes
- Resolving agent configurations (LLM, role, tone, prompt)
- Connecting edges according to their types (sequential, conditional, feedback, interjection, injects_config)
- Returning a `CompiledWorkflow` object with the compiled graph and agent resolutions.

### Internal functions

- `_detect_cycle` – DFS‑based cycle detection for non‑feedback edges; returns the cycle path or `None`.
- `_validate_graph` – validates connectivity, node requirements, and edge validity.
- `_validate_tone_profile_edges` – enforces the injects_config edge constraints.

---

## Schema Migrations (`migrations.py`)

Manages SQLite schema evolution. The current schema version is **28**.

### How it works

- A `schema_version` table tracks applied migrations (one row per version).
- `run_migrations(db_path)` reads the current version and applies all pending migrations in order.
- Each migration is a list of SQL statements (CREATE TABLE, ALTER TABLE, INSERT…) wrapped in a version block.
- Migrations are designed to be idempotent: `CREATE TABLE IF NOT EXISTS`, `INSERT OR IGNORE`, and `ALTER TABLE` with try/except for columns that may already exist.

### Notable migration groups

| Versions | What they introduce |
|---|---|
| v1–v3 | Core blueprint tables (LLM profiles, prompts, roles, agent blueprints, canvas layouts, role types) |
| v4 | Graph columns on workflow_definitions (nodes JSON, edges JSON, entry point, termination conditions) |
| v5–v6 | Workflow sessions, audit log, report jobs, immutability flags |
| v7 | A2A protocol fields on LLM profiles |
| v8 | `role_type_id` on role_definitions |
| v9–v10 | Workflow templates, tone profiles |
| v11 | Output composer (debate artifacts, render jobs, TTS voices, optimization proposals) |
| v12 | Input composer (input jobs, A2A inbound tasks, debate inputs) |
| v13–v15 | Profile types, seed role types, TTS voice on blueprints |
| v19–v25 | Module registry, translation cache, audit content columns, trace log path, service eligibility |
| v26–v27 | Agent bundles, prompt modifiers |

---

## Integration Points

| External component | How it uses the blueprints package |
|---|---|
| **Builder UI (frontend)** | Calls repository and composer endpoints via API routers (e.g., `api/routers/bundle_composer.py`) |
| **Workflow engine** (`backend/workflow`) | Receives compiled `WorkflowDefinition` and `CompiledWorkflow` from `CompilerService.compile_to_langgraph()` |
| **Module system** (`backend/services/composer_service`, `backend/services/module_profile_sync`) | Loads module content from filesystem; `BundleComposer` calls these to resolve components at runtime |
| **LLM interaction** | The resolved `ResolvedAgent` objects provide the actual LLM profile, role definition, and prompt template to the execution layer |
| **MVP debate canvas** (`backend/blueprints/mvp_debate_canvas.py`) | Uses repository and module sync to quickly scaffold a standard debate workflow; also calls internal helpers like `_ensure_role_type` and `_ensure_role_definition` |

## Key Design Decisions

- **Repository pattern** – All persistence is abstracted behind `BlueprintRepository`. Services never touch SQL directly.
- **No inline content duplication** – Composer bundles store only module IDs; content is loaded from the module filesystem at resolve time.
- **Conflict strategy during import** – `ImportConflictStrategy.RENAME` is the default, generating new IDs to avoid collisions when importing into systems with overlapping IDs.
- **Separation of visual and executable models** – `CanvasLayout` is a visual graph with positions; `WorkflowDefinition` is the executable graph. The conversion is a one‑way transformation.
- **Validation without compilation** – `CompilerService.compile()` performs thorough validation without the overhead of LangGraph construction. `compile_to_langgraph()` adds the graph building step only when needed.