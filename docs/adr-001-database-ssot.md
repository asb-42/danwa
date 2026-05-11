# ADR-001: Database as Single Source of Truth for Blueprint Entities

## Status

**Accepted** — Implemented in commits 78a4cee (profiles), 6f34ecf (LLM profiles UI), 770bb50 (canvas edge wiring).

## Date

2026-05-10

## Context

The danwa platform manages three core configuration domains that drive debate workflows:

1. **LLM Profiles** — API keys, models, providers, parameters
2. **Agent Personas** — Role definitions with behavioral constraints
3. **Prompt Templates** — Per-role prompt content with variants

Before this decision, these domains were managed by two parallel, uncoordinated systems:

| System | Storage | Consumers |
|--------|---------|-----------|
| [`ProfileService`](backend/services/profile_service.py) | YAML files (`profiles/llm/*.yaml`, `profiles/agents/*.yaml`, `profiles/prompts/`) | `LLMService`, workflow nodes, Config UI |
| [`BlueprintRepository`](backend/blueprints/repository.py) | SQLite DB (`data/blueprints.db`) | Blueprint Canvas UI |

### The Problem

Both systems could store the same entity ID with different values. This caused:

1. **Data divergence**: A profile edited in the Blueprint Canvas was invisible to the workflow runtime, which read from YAML.
2. **401 Unauthorized errors**: The Xiaomi LLM profile had a stale API key in YAML while the DB had the correct one (fixed in a prior sprint).
3. **No relational integrity**: YAML files couldn't enforce foreign keys (e.g., `RoleDefinition.role_type_id → RoleType.id`), leading to orphaned references.
4. **Duplicate edit surfaces**: Users could edit the same entity in both Config UI and Blueprint Canvas, with last-write-wins and no conflict detection.
5. **Prompt content fragmentation**: Prompt text lived in filesystem `.md` files, while metadata lived in the DB. Editing one didn't update the other.

### Alternatives Considered

#### Alternative A: YAML as SSOT (status quo)

Keep YAML files as primary, add sync from YAML → DB on startup.

- **Pros**: No migration needed, familiar to ops teams.
- **Cons**: No relational queries, no transactional writes, no referential integrity. YAML parsing is slow at scale. Canvas edits must be serialized back to YAML (lossy for rich metadata).

#### Alternative B: Dual-write with CRDT conflict resolution

Write to both systems concurrently, use vector clocks to resolve conflicts.

- **Pros**: Supports offline editing, eventual consistency.
- **Cons**: Massive complexity increase. No real use case for offline editing in a debate platform. CRDT libraries for Python/Svelte are immature.

#### Alternative C: Database as Single Source of Truth (chosen)

Make `blueprints.db` the authoritative store. YAML/filesystem = seed source and backup.

- **Pros**: Relational integrity, transactional writes, single API surface, Canvas ↔ Runtime parity.
- **Cons**: Requires migration for existing deployments (handled by seed-on-first-load pattern).

## Decision

**`blueprints.db` (SQLite) is the Single Source of Truth for all three domains: LLM profiles, agent personas (role definitions), and prompt content.**

### Key Design Principles

1. **DB-first reads**: [`ProfileService`](backend/services/profile_service.py:95) reads from `blueprints.db` first. If the DB is empty, falls back to YAML/filesystem and seeds the DB.

2. **Dual-write on save**: [`save_llm_profile()`](backend/services/profile_service.py:406) writes to both DB (primary) and YAML (backup). This ensures backward compatibility and provides a human-readable backup.

3. **Dual-delete on remove**: [`delete_llm_profile()`](backend/services/profile_service.py:442) deletes from both DB and YAML.

4. **Legacy converters**: [`BlueprintLLMProfile.to_legacy()`](backend/blueprints/models.py:130) and [`RoleDefinition.to_legacy()`](backend/blueprints/models.py:260) convert DB models to the legacy `LLMProfile`/`AgentPersona` schemas consumed by `LLMService` and workflow nodes.

5. **Content cache**: Prompt content from `prompt_templates` is cached in [`_prompt_content_cache`](backend/services/profile_service.py:56) keyed by `db:variant/role/lang` to avoid repeated DB queries during workflow execution.

6. **Canvas edge wiring**: Semantic edges on the Blueprint Canvas (`defines_role`, `implements_role`, `uses_llm`, `prompted_by`, `overrides_prompt`) update DB FK fields directly via [`edgeWiring.js`](frontend/src/lib/blueprint/edgeWiring.js), making Canvas edits immediately visible to the workflow runtime.

### Data Flow

```
                    ┌─────────────────────────────────────┐
                    │          blueprints.db              │
                    │                                     │
  YAML/MD files ──→ │  blueprint_llm_profiles             │
  (seed/import)     │  role_definitions                   │
                    │  role_types                         │
  Blueprint Canvas ─│─→ prompt_templates                  │──→ ProfileService ──→ LLMService
  (edge wiring)     │  agent_blueprints                   │──→ PromptService  ──→ Workflow Nodes
                    │  canvas_layouts                     │
  Config UI ────────│─→ workflow_definitions               │
  (CRUD API)        │                                     │
                    └─────────────────────────────────────┘
                                    │
                                    ▼ (backup)
                            YAML files + .md files
```

### Migration Strategy

| Step | Action | Trigger |
|------|--------|---------|
| 1 | Seed YAML → DB | First startup if DB table is empty |
| 2 | Seed prompts → DB + content cache | First startup if `prompt_templates` is empty |
| 3 | Seed default role types | Migration v14 (6 built-in types) |
| 4 | Runtime reads from DB | All subsequent startups |

No manual migration required. The seed-on-first-load pattern ensures existing deployments continue working without intervention.

## Consequences

### Positive

- **Single source of truth**: No more data divergence between Canvas and Runtime.
- **Relational integrity**: FK constraints prevent orphaned references.
- **Transactional writes**: Multi-field updates are atomic (e.g., updating `role_type_id` and `consensus_threshold` together).
- **Query capabilities**: JOIN queries for "show all agents using this LLM profile" or "find orphaned role definitions."
- **Canvas → Runtime parity**: Edge wiring updates the DB, which the runtime reads. Edges are no longer visual-only.
- **Backup safety**: YAML files are still written as backup, providing human-readable disaster recovery.

### Negative

- **SQLite concurrency**: SQLite uses file-level locking. Under heavy concurrent writes (e.g., multiple Canvas users), writes may block. Mitigated by short write transactions and WAL mode.
- **Migration complexity**: Existing deployments need a one-time seed. Mitigated by the automatic fallback pattern.
- **Dual-write overhead**: Every save writes to two systems. Acceptable for the low write volume of a debate platform.
- **Legacy model coupling**: `to_legacy()` converters must be maintained as long as `LLMService` and `PromptService` use the legacy schemas.

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| DB schema evolution breaks seed | Low | High | Migrations tested in CI, versioned schema |
| YAML backup out of sync | Medium | Low | Backup is best-effort, not authoritative |
| SQLite lock contention | Low | Medium | WAL mode, short transactions |
| `to_legacy()` conversion bug | Medium | High | Comprehensive test coverage (84+ tests) |

## References

- [ProfileService → DB SSOT Plan](../plans/profile-service-db-ssot.md)
- [Canvas-based Role Assignment Plan](../plans/canvas-role-assignment.md)
- [Blueprint Canvas Phase 1-4 Docs](../docs/blueprint-canvas-phase1.md)
- Commit 78a4cee: Agent Personas + Prompts → DB SSOT
- Commit 770bb50: Phase 1 — Edge → Backend Wiring
