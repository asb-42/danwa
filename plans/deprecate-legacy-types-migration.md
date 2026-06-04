# Migration Plan: Deprecate RoleType, AgentPersona, PromptVariant

## User Decisions
- Agent-Cores do NOT need `icon` or `color` — canvas uses hardcoded defaults per role name
- `max_rounds` and `consensus_threshold` on RoleType/AgentPersona are **dead code at runtime** — values come from the debate request, not from legacy types. Deprecate.
- Agent-Cores do NOT need `default_max_rounds` or `default_consensus_threshold` — same reason

## Property Gap Analysis (Revised)

### What Agent Core modules absorb from legacy types:
- `role` → already in manifest ✅
- `system_prompt` → in profile.md ✅
- `description` → in manifest ✅
- `tags` → in manifest ✅

### What is NOT needed (confirmed dead code):
- ~~icon~~ — canvas uses hardcoded defaults
- ~~color~~ — canvas uses hardcoded defaults
- ~~category~~ (functional/formative) — only used in prompt assembly hint, can be derived from role
- ~~default_max_rounds~~ — debate-level only
- ~~default_consensus_threshold~~ — debate-level only
- ~~max_rounds~~ — debate-level only
- ~~consensus_threshold~~ — debate-level only
- ~~llm_profile_id~~ — now in bundle composition
- ~~argumentation_pattern~~ — now separate module type
- ~~mode~~ — deprecated

### Conclusion: NO manifest schema changes needed!
Agent-core modules already have everything needed. The migration is purely about routing — making the debate workflow and canvas load from modules instead of legacy DB tables.

---

## Execution Phases

### Phase 1: Dual-Path Resolution (Non-Breaking)
Make debate workflow work with BOTH legacy and module sources.

### Phase 2: UI Migration (Non-Breaking)
Replace ManageView legacy tabs with module-based management.

### Phase 3: Legacy Removal (Breaking)
Remove legacy types, API endpoints, DB tables, frontend components.
