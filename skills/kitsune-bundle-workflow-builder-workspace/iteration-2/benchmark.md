# Benchmark: kitsune-bundle-workflow-builder — Iteration 2

## Ergebnis: 100% 🎉

| Config | Pass Rate | Passed / Total |
|---|---|---|
| **With skill v2 (korrigiert)** | **100%** | 18 / 18 |

## Vergleich Iteration 1 → 2

| Eval | Iteration 1 (v1) | Iteration 2 (v2) | Δ |
|---|---|---|---|
| Bundle erstellen | 83% | **100%** | +17% |
| Template bauen | 100% | **100%** | 0% |
| Bundle editieren | 100% | **100%** | 0% |
| **Gesamt** | **93.75%** | **100%** | **+6.25%** |

## Was sich verbessert hat

Das einzige Problem in Iteration 1 war die `role_type_id`:
- ❌ v1: `"analyst"` (fälschlich aus `agent_core_id` deriviert)
- ✅ v2: `"ux-researcher"` (zum Rollennamen passend)

Die restlichen Fehler der Without-Skill-Baseline (falsche Feldnamen, unnötige Platzhalter) traten in der With-Skill-Version nie auf — die Skill hat diese Aspekte von Anfang an richtig gemacht.
