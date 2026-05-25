# Benchmark: kitsune-bundle-workflow-builder — Iteration 1

## Summary

| Config | Pass Rate | Passed / Total |
|---|---|---|
| **With skill** | **93.75%** | 15 / 16 |
| **Without skill (baseline)** | **81.25%** | 13 / 16 |
| **Delta** | **+12.5%** | |

## Per-Eval Breakdown

### Eval 0: create-ux-researcher-bundle

| Assertion | With Skill | Without Skill |
|---|---|---|
| Manifest type is 'bundle' | ✅ | ✅ |
| Manifest category is 'bundles' | ✅ | ✅ |
| Manifest profile_format is 'json' | ✅ | ✅ |
| Module ID starts with 'bundle-' | ✅ | ✅ |
| Profile exists with valid JSON | ✅ | ✅ |
| role_type_id matches role name | ❌ `analyst` | ✅ `ux-researcher` |

### Eval 1: create-3-phase-template

| Assertion | With Skill | Without Skill |
|---|---|---|
| Has 3 wf-phase nodes | ✅ | ✅ |
| Has 6 wf-agent nodes | ✅ | ✅ |
| Has wf-gate nodes | ✅ | ✅ |
| Agent parent_id set | ✅ `parent_id` | ❌ `container` |
| bundle_id field used | ✅ (top-level) | ❌ `agent_bundle_id` |
| termination_conditions | ✅ | ✅ |
| entry_point valid | ✅ | ✅ |
| No unnecessary placeholders | ✅ (empty) | ❌ (6 bundle refs) |

### Eval 2: edit-bundle-analyst-pattern

| Assertion | With Skill | Without Skill |
|---|---|---|
| pattern changed to debate-analyst | ✅ | ✅ |
| Other fields preserved | ✅ | ✅ |

## Key Observations

1. **Template-Erstellung: +37.5% Skill-Mehrwert** (grösster Impact)
2. **With-Skill-Schwäche**: role_type_id fälschlich aus agent_core_id deriviert (Part before first hyphen)
3. **Without-Skill-Schwächen**: Falsche Feldnamen (agent_bundle_id, container) + unnötige Platzhalter
4. **Beide gleich gut bei**: einfachen Edit-Aufgaben

## Changes Applied to Skill (Iteration 1 → 2)

- ✅ role_type_id = Rollenname (nicht agent_core_id-Derivat)
- ✅ bundle_id auf oberster Node-Ebene (nie in config) + Warnhinweis
- ✅ Gate→Phase/Output = conditional (nie sequential) + Beispiel-Pattern
- ✅ Validierungs-Checkliste erweitert
