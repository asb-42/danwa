# Agent Bundle Schema Reference

## Directory Structure

```
modules/agent-bundles/bundle-{role}/
├── manifest.json    # Required
└── profile.json     # Required (profile_format=json)
```

## manifest.json

```json
{
  "schema_version": "2.0.0",
  "module_id": "bundle-{role}",
  "name": { "en": "Role Name (Default)" },
  "description": { "en": "Description of this bundle." },
  "version": "1.0.0",
  "type": "bundle",
  "category": "bundles",
  "author": { "name": "Danwa Community" },
  "license": "CC-BY-4.0",
  "tags": ["rolename", "default", "multi-phase"],
  "language": "en",
  "profile_file": "profile.json",
  "profile_format": "json",
  "dependencies": {
    "agent-cores/{agent-core-id}": ">=1.0.0"
  }
}
```

## profile.json

```json
{
  "id": "bundle-{role}",
  "name": "Role Name (Default)",
  "description": "Description of this bundle.",
  "llm_profile_id": "default",
  "role_type_id": "{role}",
  "composition": {
    "agent_core_id": "{agent-core-id}",
    "argumentation_pattern_id": "{pattern-id}",
    "prompt_modifier_id": "prompt-modifier-neutral-default"
  },
  "is_active": true
}
```

## Fields Explained

### manifest.json
- `module_id`: Must match directory name after `bundle-` prefix. Globally unique.
- `type`: Always `"bundle"` — tells the system this is an agent bundle module.
- `category`: Always `"bundles"` — determines which tab it appears in.
- `profile_format`: Always `"json"` for bundles (not `"md"` like agent-persona).
- `profile_file`: Always `"profile.json"`.
- `dependencies`: Maps `agent-cores/{core_id}` to version constraint. The key is the module_id of the agent core this bundle depends on.

### profile.json
- `id`: Same as `module_id` in manifest.
- `role_type_id`: Human-readable role identifier (e.g., `analyst`, `creative-thinker`). Should match the role name, not mechanically derived from agent_core_id. The `_resolve_role_type_id` function takes `parts[0]`, which is only used by the programmatic BundleComposer — for filesystem bundles, the value is used as-is from profile.json.
- `llm_profile_id`: Usually `"default"`. References an LLM profile module.
- `composition.agent_core_id`: Module ID of the agent core (e.g., `"analyst-default"`). Bundles bundle a specific agent core with its argumentation pattern and prompt modifier.
- `composition.argumentation_pattern_id`: Module ID of the argumentation pattern (e.g., `"strategist"`, `"debate-analyst"`).
- `composition.prompt_modifier_id`: Module ID of the prompt modifier. Usually `"prompt-modifier-neutral-default"` unless the role needs a specific modifier.

## Naming Convention

| Directory | role_type_id | module_id |
|---|---|---|
| `bundle-analyst/` | `analyst` | `bundle-analyst` |
| `bundle-creative-thinker/` | `creative-thinker` | `bundle-creative-thinker` |
| `bundle-devils-advocate/` | `devils-advocate` | `bundle-devils-advocate` |
| `bundle-moderator/` | `moderator` | `bundle-moderator` |

The `role_type_id` in profile.json is the human-readable role name. It does NOT need to match the agent-core module_id prefix — e.g., agent_core `creative-thinker-default` gets `role_type_id: "creative-thinker"`, not `"creative"` (which `_resolve_role_type_id` would produce). Check existing bundles under `modules/agent-bundles/` for the established convention.

## Available Agent Cores

List available cores by reading `modules/agent-cores/` directories. Each has `manifest.json` with `module_id` like `"analyst-default"`.

## Existing Bundles (for reference)

All 15 bundles follow this pattern:

| Bundle | agent_core_id | argumentation_pattern_id |
|---|---|---|
| bundle-analyst | analyst-default | strategist |
| bundle-creative-thinker | creative-thinker-default | strategist |
| bundle-socratic-questioner | socratic-questioner-default | strategist |
| bundle-strategist | strategist-default | strategist |
| bundle-expert-reviewer | expert-reviewer-default | strategist |
| bundle-steel-manner | steel-manner-default | strategist |
| bundle-devils-advocate | devils-advocate-default | strategist |
| bundle-fact-checker | fact-checker-default | strategist |
| bundle-troll | troll-default | strategist |
| bundle-mediator | mediator-default | strategist |
| bundle-ethicist | ethicist-default | strategist |
| bundle-synthesizer | synthesizer-default | strategist |
| bundle-moderator | moderator-default | strategist |
| bundle-critic | critic-default | strategist |
| bundle-optimizer | optimizer-default | strategist |
