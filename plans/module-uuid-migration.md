# Module ID → UUID Migration Plan ✅ (completed 2026-06-05)

## Problem

Module IDs are currently slug-derived from directory names, leading to:
- **No stable identity**: renaming a directory changes the ID
- **Copy-of-copy chaos**: `critic-default`, `critic-enhanced`, `critic-example`, `critic-stoic`
- **Inconsistent conventions**: `agent-strategist-default-en` vs `workflow-tpl-5-phase-debate` vs `llm-0d14655f-...`
- **`module_id` vs `profile_id` confusion**: Agent cores have TWO different slug IDs (`agent-strategist-default-en` in manifest, `strategist-default-en` as `profile_id`)

## Goal

Every module gets a UUID as its stable, immutable identity — following the LLM profile pattern that already works.

## Reference: LLM Profile Pattern (already correct)

```
modules/llm-profiles/
  llm-0d14655f-c0a9-42ac-b62a-6cc23854e371/
    manifest.json  →  "module_id": "llm-0d14655f-c0a9-42ac-b62a-6cc23854e371"
    profile.yaml   →  "id": "0d14655f-c0a9-42ac-b62a-6cc23854e371"
```

- Directory name = `{type-prefix}-{uuid}/`
- `module_id` = `{type-prefix}-{uuid}`
- Entity `id` in profile = the UUID (without prefix)
- Human-readable metadata lives in `name` and `description` (localized dicts)

## New ID Convention (all module types)

| Module type | Prefix | Directory pattern | module_id pattern |
|---|---|---|---|
| Agent core | `ac` | `ac-{uuid}/` | `ac-{uuid}` |
| Workflow template | `wt` | `wt-{uuid}/` | `wt-{uuid}` |
| LLM profile | `llm` | `llm-{uuid}/` | `llm-{uuid}` (already done) |
| Tone profile | `tp` | `tp-{uuid}/` | `tp-{uuid}` |
| Argumentation pattern | `ap` | `ap-{uuid}/` | `ap-{uuid}` |
| Prompt modifier | `pm` | `pm-{uuid}/` | `pm-{uuid}` |
| Prompt variant | `pv` | `pv-{uuid}/` | `pv-{uuid}` |
| Role type | `rt` | `rt-{uuid}/` | `rt-{uuid}` |
| Bundle | `bd` | `bd-{uuid}/` | `bd-{uuid}` |
| Language pack | `lp` | `lp-{uuid}/` | `lp-{uuid}` |
| Kitsune assistant | `ka` | `ka-{uuid}/` | `ka-{uuid}` |

## Migration Strategy

### Phase A: Backend Infrastructure (danwa) ✅

1. **Update `ModuleManifest.module_id` regex** in [`models.py`](backend/modules/models.py:187)
   - Old: `r"^[a-z][a-z0-9.-]*$"`
   - New: `r"^[a-z]{2}-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"`
   - Or more relaxed: `r"^[a-z][a-z0-9-]*$"` (keep hyphens, drop dots/underscores)

2. **Remove `profile_id` as separate concept** in [`module_profile_sync.py`](backend/services/module_profile_sync.py:204)
   - Agent cores: `"id": manifest.get("profile_id", ...)` → `"id": mod["module_id"]`
   - All entity types use `module_id` as their stable identity
   - Remove the `MODULE_TYPE_ID_FIELD` mapping (line 27-35)

3. **Update `type_derivation.py`** — prefix-based type detection
   - `ac-*` → `AGENT_PERSONA`
   - `wt-*` → `WORKFLOW_TEMPLATE`
   - `llm-*` → `LLM_PROFILE`
   - etc.
   - Keep directory-based detection as fallback

4. **Update `ModuleService._resolve_module_dir()`** — search by `module_id` in manifest, not directory name

5. **Update module registry DB migration** — rename existing entries from old slug IDs to new UUIDs

### Phase B: Module Manifests (danwa-modules + local) ✅

For each module of each type, generate a UUID and update:

1. **Rename directory**: `strategist-default/` → `ac-{uuid}/`
2. **Update manifest.json**:
   - `"module_id": "ac-{uuid}"`
   - Remove `"profile_id"` (no longer needed — `module_id` IS the identity)
   - Keep `role`, `name`, `description`, `tags` (human-readable metadata)
   - Update `checksum`
3. **Keep profile file unchanged** (`profile.md`, `profile.yaml`, `profile.json`)

### Phase C: Template & Frontend Updates (danwa) ✅ (no changes needed — role-based resolution)

1. **Templates** — No changes needed
   - `default_role` resolves by role, not by module_id
   - The role-based resolution in [`workflow_templates.py`](backend/api/routers/workflow_templates.py:180) uses `mp.get("role")`, not `mp.get("id")`

2. **Frontend ModuleManager** — Display `name.en` instead of `module_id`
   - Module cards already show localized names
   - Internal references use `module_id` (now UUID) — no visible change

3. **Frontend TemplateInstantiateModal** — Uses `default_role` resolution, no change needed

### Phase D: Index & Sync ✅

1. **Regenerate `index.json`** — new `module_id` values
2. **Update `generate_index.py`** — already reads from manifest, just regenerate
3. **Clear module registry DB** on upgrade — fresh install of all modules with new IDs

## Scope — Module Counts

### danwa-modules (canonical)

| Type | Count | Status |
|---|---|---|
| Agent cores | ~34 | Need UUID migration |
| Workflow templates | 8 | Need UUID migration |
| LLM profiles | ~21 | Already UUID-based ✓ |
| Tone profiles | ~5 | Need UUID migration |
| Argumentation patterns | ~5 | Need UUID migration |
| Prompt modifiers | ~5 | Need UUID migration |
| Bundles | ~15 | Need UUID migration |
| Language packs | ~55 | Need UUID migration |
| Kitsune assistant | ~1 | Need UUID migration |

### danwa (local copies)

Same modules mirrored locally in `modules/`.

## Migration Script

A Python script (`scripts/migrate_module_uuids.py`) that:

1. Scans all module directories
2. Generates a deterministic UUID per module (based on `module_id` + salt) for reproducibility
3. Renames directories
4. Updates `manifest.json` files
5. Removes `profile_id` fields
6. Updates `checksum` fields
7. Regenerates `index.json`

**Deterministic UUID**: `uuid5(DANWA_NAMESPACE, old_module_id)` — same old ID always maps to same UUID, so multiple environments stay in sync.

## Breaking Changes

- **Module registry DB**: All existing installed modules need re-installation (old IDs won't match)
- **Direct API consumers**: Any code referencing `module_id` values by string
- **Export/Import bundles**: Old exports with slug IDs won't match new UUIDs
- **Canvas layouts**: Saved layouts referencing blueprints by old module IDs

## Rollout

1. Merge Phase A (backend) to `main`
2. Run migration script on `danwa-modules`, commit & push
3. Run migration script on `danwa` local modules, commit & push
4. Re-seed templates
5. Clear module registry DB (or migration script handles it)
6. Restart — modules re-discovered with new UUIDs

## Architecture Diagram

```mermaid
graph TB
    subgraph Before
        OLD_MANIFEST[module_id: strategist-default-en]
        OLD_DIR[modules/agent-cores/strategist-default/]
        OLD_PROFILE_ID[profile_id: strategist-default-en]
        OLD_MANIFEST --> OLD_DIR
        OLD_MANIFEST --> OLD_PROFILE_ID
    end

    subgraph After
        NEW_MANIFEST[module_id: ac-550e8400-e29b-41d4-a716-446655440000]
        NEW_DIR[modules/agent-cores/ac-550e8400-e29b-41d4-a716-446655440000/]
        NEW_ROLE[role: strategist]
        NEW_NAME[name.en: Default Strategist]
        NEW_MANIFEST --> NEW_DIR
        NEW_MANIFEST --> NEW_ROLE
        NEW_MANIFEST --> NEW_NAME
    end

    OLD_MANIFEST -->|UUID migration script| NEW_MANIFEST
    OLD_DIR -->|rename| NEW_DIR
    OLD_PROFILE_ID -->|removed| NEW_MANIFEST
