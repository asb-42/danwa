# Blueprint Canvas — Phase 1: Domain Models & Data Migration

## Overview

Phase 1 establishes the foundational data layer for the Blueprint Canvas feature. It introduces a new `backend/blueprints/` package containing Pydantic-V2 domain models, SQLite schema migrations, a repository with full CRUD operations, and an idempotent importer that migrates existing YAML/MD configuration files into the new Blueprint system.

## Package Structure

```
backend/blueprints/
├── __init__.py        # Public exports
├── models.py          # Pydantic-V2 domain models
├── migrations.py      # SQLite schema (schema_version + 5 entity tables)
├── repository.py      # BlueprintRepository — CRUD for all entity types
└── importer.py        # BlueprintImporter — idempotent YAML/MD import
```

## Domain Models

### BlueprintLLMProfile

Represents an LLM endpoint configuration (provider, model, API key, parameters).

- **Fields**: `id`, `name`, `provider`, `model`, `api_base`, `api_key_env`, `max_tokens`, `context_window`, `temperature`, `timeout`, `cost_per_1k_input`, `cost_per_1k_output`, `description`, `tags`, `is_a2a`, `created_at`, `updated_at`
- **Validators**: `temperature` (0–2), `max_tokens` (>0), `id` (pattern: `[a-z0-9][a-z0-9._-]*`)
- **Legacy conversion**: `from_legacy(LLMProfile)` / `to_legacy() → LLMProfile`

### PromptTemplate

Stores prompt content inline with content-hash-based change detection.

- **Fields**: `id`, `name`, `role`, `content`, `language`, `variant`, `description`, `tags`, `source_path`, `content_hash`, `created_at`, `updated_at`
- **Validators**: `content` must not be empty; `content_hash` auto-computed via SHA-256 (first 16 hex chars)
- **Roles**: `strategist`, `critic`, `optimizer`, `moderator`

### RoleDefinition

Defines an agent role with behavioral parameters.

- **Fields**: `id`, `name`, `role`, `system_prompt`, `max_rounds`, `consensus_threshold`, `prompt_template_id`, `description`, `tags`, `created_at`, `updated_at`
- **Validators**: `consensus_threshold` (0–1)
- **Legacy conversion**: `from_legacy(AgentPersona, prompt_template_id=None)`

### AgentBlueprint

Composite entity linking an LLM profile, role definition, and optional prompt template override.

- **Fields**: `id`, `name`, `llm_profile_id`, `role_definition_id`, `prompt_template_id`, `is_active`, `description`, `tags`, `created_at`, `updated_at`
- **Relationships**: References `BlueprintLLMProfile`, `RoleDefinition`, and optionally `PromptTemplate` by ID

### CanvasLayout + Sub-models

Persists canvas node positions, edges, and viewport state.

- **CanvasLayout**: `id` (auto-generated 8-char), `name`, `project_id`, `layout_data`, `created_at`, `updated_at`
- **CanvasLayoutData**: `nodes[]`, `edges[]`, `viewport`
- **CanvasLayoutNode**: `id`, `type`, `x`, `y`, `data`
- **CanvasLayoutEdge**: `id`, `source`, `target`, `type`, `data`
- **CanvasLayoutViewport**: `x`, `y`, `zoom` (default 1.0)

## SQLite Schema

Database location: `data/blueprints.db` (configurable via `BlueprintRepository(db_path=...)`)

### Schema Versioning

A `schema_version` table tracks the current version. `run_migrations()` applies all pending migrations idempotently using `CREATE TABLE IF NOT EXISTS`.

### Tables

| Table | Foreign Keys | Notes |
|-------|-------------|-------|
| `blueprint_llm_profiles` | — | LLM endpoint configs |
| `prompt_templates` | — | Inline prompt content with content_hash |
| `role_definitions` | `prompt_template_id → prompt_templates(id)` | ON DELETE SET NULL |
| `agent_blueprints` | `llm_profile_id`, `role_definition_id`, `prompt_template_id` | ON DELETE CASCADE for profile/role, SET NULL for prompt |
| `canvas_layouts` | — | JSON-serialized layout data |

## Repository

[`BlueprintRepository`](backend/blueprints/repository.py) provides synchronous CRUD for all 5 entity types:

- `save_*` / `get_*` / `list_*` / `delete_*` for each entity
- Uses `sqlite3.Row` for column access
- `PRAGMA foreign_keys=ON` enforced on every connection
- List methods support filtering (e.g., `list_prompt_templates(role=..., variant=...)`, `list_blueprints(active_only=True)`)

## Importer

[`BlueprintImporter`](backend/blueprints/importer.py) performs idempotent imports from existing configuration files.

### Import Sources

| Source | Entity Type | Format |
|--------|------------|--------|
| `profiles/llm/*.yaml` | BlueprintLLMProfile | New YAML format |
| `archive/config/llm_profiles.yaml` | BlueprintLLMProfile | Legacy nested `profiles:` format |
| `profiles/agents/*.yaml` | RoleDefinition | Agent persona YAML |
| `profiles/prompts/default/*.md` | PromptTemplate (variant=default) | Markdown |
| `profiles/prompts/variants/*/*.md` | PromptTemplate (variant=derived) | Markdown |
| `archive/config/prompts/*.md` | PromptTemplate (variant=archive) | Markdown |

### Idempotency

Each import computes a `content_hash` (SHA-256, 16 hex chars) for the entity content. On re-import:
- **Same hash** → skip (counted as `skipped`)
- **Different hash** → update (counted as `updated`)
- **New entity** → create (counted as `created`)

### No Auto-Assembly

The importer creates individual entities (profiles, roles, prompts) but does **not** create `AgentBlueprint` composites. Assembly is a user-driven action in Phase 3.

## Tests

57 tests across 12 test classes in [`tests/backend/test_blueprints.py`](tests/backend/test_blueprints.py):

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestBlueprintLLMProfile | 7 | Model validation, providers, timestamps |
| TestPromptTemplate | 4 | Creation, empty content, content_hash |
| TestRoleDefinition | 4 | Creation, threshold validation, optional prompt |
| TestAgentBlueprint | 2 | Creation, optional prompt override |
| TestCanvasLayout | 2 | Defaults, with data |
| TestLegacyConversion | 5 | from_legacy, to_legacy, roundtrip |
| TestBlueprintRepositoryLLMProfiles | 6 | CRUD, upsert, nonexistent |
| TestBlueprintRepositoryPromptTemplates | 4 | CRUD, filter by role/variant |
| TestBlueprintRepositoryRoleDefinitions | 3 | CRUD, filter by role |
| TestBlueprintRepositoryAgentBlueprints | 3 | CRUD, active_only filter |
| TestBlueprintRepositoryCanvasLayouts | 4 | CRUD, project filter, empty roundtrip |
| TestBlueprintImporter | 13 | All import sources, idempotency, dry_run, update detection, empty dirs |

## Running

```bash
# Tests
uv run pytest tests/backend/test_blueprints.py -v

# Lint
uv run ruff check backend/blueprints/ tests/backend/test_blueprints.py
```

## What's Next

Phase 2 adds the REST API layer:
- FastAPI routers for all 5 entity types + import endpoint
- Error handlers (404, 409, 422)
- Pagination for list endpoints
- API-level tests

See [`plans/blueprint-canvas-phase2.md`](../plans/blueprint-canvas-phase2.md) for the full plan.
