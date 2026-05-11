# ProfileService → DB Single Source of Truth

## Problem

Two parallel systems manage LLM profiles:

| System | Storage | Used by |
|--------|---------|---------|
| `ProfileService` | YAML files (`profiles/llm/*.yaml`) | `LLMService`, workflow nodes, Config UI |
| `BlueprintRepository` | SQLite DB (`data/blueprints.db`) | Blueprint Canvas UI |

Both can store the same profile ID with different values → conflicts, stale data, 401 errors.

## Goal

**`blueprints.db` = Single Source of Truth** for LLM profiles.  
YAML files = seed/import source only (loaded once if DB is empty).

## Architecture

### Current Flow (broken)
```
YAML files ──→ ProfileService ──→ LLMService ──→ Workflow
Blueprint Canvas ──→ BlueprintRepository ──→ blueprints.db (never read by workflow!)
```

### Target Flow (SSOT)
```
YAML files ──→ Importer ──→ blueprints.db (seed only)
Blueprint Canvas ──→ BlueprintRepository ──→ blueprints.db
ProfileService ──→ reads from blueprints.db ──→ LLMService ──→ Workflow
```

## Changes

### 1. `ProfileService.__init__()` — add `db_path` parameter

```python
def __init__(
    self,
    profile_dir: Path | str = _DEFAULT_PROFILE_DIR,
    project_config: ProjectConfig | None = None,
    db_path: Path | str | None = None,  # NEW
):
    self.profile_dir = Path(profile_dir)
    self._project_config = project_config
    self._db_path = Path(db_path) if db_path else Path("data/blueprints.db")
    self._llm_cache: dict[str, LLMProfile] = {}
    self._agent_cache: dict[str, AgentPersona] = {}
    self._prompt_cache: dict[str, PromptVariant] = {}
    self._loaded = False
```

### 2. `_load_llm_profiles()` — read from DB first, fallback to YAML seed

```python
def _load_llm_profiles(self) -> None:
    from backend.blueprints.repository import BlueprintRepository
    from backend.blueprints.models import BlueprintLLMProfile

    # Try loading from DB
    try:
        repo = BlueprintRepository(self._db_path)
        db_profiles = repo.list_llm_profiles(limit=500)
        if db_profiles:
            for bp in db_profiles:
                legacy = bp.to_legacy()  # BlueprintLLMProfile → LLMProfile
                self._llm_cache[legacy.id] = legacy
            logger.info("Loaded %d LLM profiles from DB", len(db_profiles))
            return
    except Exception:
        logger.warning("Could not load LLM profiles from DB, falling back to YAML")

    # Fallback: load from YAML and seed into DB
    self._load_llm_profiles_from_yaml()
    self._seed_yaml_to_db()
```

### 3. `_load_llm_profiles_from_yaml()` — extract current YAML loading logic

```python
def _load_llm_profiles_from_yaml(self) -> None:
    llm_dir = self.profile_dir / "llm"
    if not llm_dir.is_dir():
        return
    for yaml_file in sorted(llm_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            profile = LLMProfile(**data)
            self._llm_cache[profile.id] = profile
        except Exception:
            logger.exception("Failed to load LLM profile from %s", yaml_file)
```

### 4. `_seed_yaml_to_db()` — one-time import

```python
def _seed_yaml_to_db(self) -> None:
    if not self._llm_cache:
        return
    try:
        from backend.blueprints.repository import BlueprintRepository
        from backend.blueprints.models import BlueprintLLMProfile

        repo = BlueprintRepository(self._db_path)
        for profile in self._llm_cache.values():
            bp = BlueprintLLMProfile.from_legacy(profile)
            repo.save_llm_profile(bp)
        logger.info("Seeded %d LLM profiles into DB", len(self._llm_cache))
    except Exception:
        logger.exception("Failed to seed LLM profiles to DB")
```

### 5. `save_llm_profile()` — write to DB + YAML

```python
def save_llm_profile(self, profile: LLMProfile) -> LLMProfile:
    self.ensure_loaded()
    # Write to DB (primary)
    from backend.blueprints.repository import BlueprintRepository
    from backend.blueprints.models import BlueprintLLMProfile

    repo = BlueprintRepository(self._db_path)
    bp = BlueprintLLMProfile.from_legacy(profile)
    repo.save_llm_profile(bp)

    # Also write to YAML (backup/compatibility)
    llm_dir = self.profile_dir / "llm"
    llm_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = llm_dir / f"{profile.id}.yaml"
    yaml_path.write_text(yaml.dump(profile.model_dump(mode="json"), ...))

    # Update cache
    self._llm_cache[profile.id] = profile
    return profile
```

### 6. `delete_llm_profile()` — delete from DB + YAML

```python
def delete_llm_profile(self, profile_id: str) -> bool:
    self.ensure_loaded()
    # Delete from DB
    from backend.blueprints.repository import BlueprintRepository
    repo = BlueprintRepository(self._db_path)
    repo.delete_llm_profile(profile_id)

    # Delete from YAML
    yaml_path = self.profile_dir / "llm" / f"{profile_id}.yaml"
    if yaml_path.exists():
        yaml_path.unlink()

    # Update cache
    return self._llm_cache.pop(profile_id, None) is not None
```

### 7. `reload()` — clear cache and reload from DB

```python
def reload(self) -> None:
    self._llm_cache.clear()
    self._agent_cache.clear()
    self._prompt_cache.clear()
    self._loaded = False
```

## Scope: What changes, what doesn't

| Component | Change? | Notes |
|-----------|---------|-------|
| `ProfileService._load_llm_profiles()` | **YES** | Read from DB, fallback to YAML |
| `ProfileService.save_llm_profile()` | **YES** | Write to both DB + YAML |
| `ProfileService.delete_llm_profile()` | **YES** | Delete from both DB + YAML |
| `ProfileService._load_agent_personas()` | **YES** | Read from `role_definitions` DB, fallback to YAML |
| `ProfileService.save_agent_persona()` | **YES** | Write to both DB + YAML |
| `ProfileService.delete_agent_persona()` | **YES** | Delete from both DB + YAML |
| `ProfileService._load_prompt_variants()` | **YES** | Read from `prompt_templates` DB, fallback to YAML |
| `ProfileService.get_prompt_content()` | **YES** | DB-first prompt content resolution |
| `ProfileService.create_prompt_variant()` | **YES** | Write to both DB + filesystem |
| `ProfileService.delete_prompt_variant()` | **YES** | Delete from both DB + filesystem |
| `PromptService` | **YES** | Delegates to `ProfileService.get_prompt_content()` for DB content |
| `_get_prompt_service()` in `nodes.py` | **YES** | Wires `ProfileService` into `PromptService` |
| `RoleDefinition.to_legacy()` | **YES** | Converts DB RoleDefinition → AgentPersona with prompt resolution |
| `LLMService` | NO | Already uses `ProfileService.get_llm_profile()` |
| Config UI (`/api/v1/profiles/`) | NO | Already uses `ProfileService` |
| Blueprint Canvas UI | NO | Already uses `BlueprintRepository` directly |
| Importer | NO | Still seeds YAML → DB |

## Migration

1. First startup after deploy: DB is populated from YAML (seed for all 3 domains)
2. Subsequent startups: DB is primary, YAML is backup
3. Blueprint Canvas edits → written to DB → immediately visible to workflow
4. Config UI edits → written to both DB + YAML

## Risks

- **DB schema evolution**: `BlueprintLLMProfile` has more fields than `LLMProfile`. The `to_legacy()` conversion handles this.
- **`RoleDefinition.to_legacy()`**: Requires prompt content resolution from `prompt_templates` table. Handled by querying DB at load time.
- **Project overrides**: Still handled by `ProjectConfig` merging on top of global profiles. No change.

## Todo

1. [x] Add `db_path` parameter to `ProfileService.__init__()`
2. [x] Refactor `_load_llm_profiles()` to read from DB with YAML fallback
3. [x] Add `_seed_yaml_to_db()` for first-run migration
4. [x] Update `save_llm_profile()` to write to both DB + YAML
5. [x] Add `RoleDefinition.to_legacy()` → `AgentPersona` converter
6. [x] Refactor `_load_agent_personas()` to read from DB with YAML fallback
7. [x] Add `_seed_agent_personas_to_db()` for first-run migration
8. [x] Update `save_agent_persona()` / `delete_agent_persona()` for DB + YAML
9. [x] Refactor `_load_prompt_variants()` to read from DB with YAML fallback
10. [x] Add `_seed_prompts_to_db()` with content cache population
11. [x] Add `get_prompt_content()` for DB-first prompt resolution
12. [x] Update `create_prompt_variant()` / `delete_prompt_variant()` for DB + filesystem
13. [x] Adapt `PromptService` to delegate to `ProfileService` for DB content
14. [x] Wire `ProfileService` into `PromptService` in `nodes.py`
15. [x] All 84 tests pass
5. Update `delete_llm_profile()` to delete from both
6. Add unit test for DB-backed profile loading
7. Test: import → DB populated → restart → profiles load from DB
8. Test: Blueprint Canvas edit → workflow sees change immediately
9. Commit & push
