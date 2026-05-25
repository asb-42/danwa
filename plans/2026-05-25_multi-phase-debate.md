# Multi-Phase Debate — Architektur- & Implementierungsplan

## Ziel

Erweiterung des Blueprint-Canvas (Workflow-Modus) um **Phasen-Container**, sodass strukturierte multi-phasige Debatten wie das 5-Phasen-Modell visuell konfiguriert werden können — ohne Dropdown-Hölle, ohne neues UI-Framework.

## Aktueller Zustand

- **Blueprint-Canvas** (`#/blueprint`) hat zwei Modi via `ModeSwitcher`: Blueprint (Asset-Nodes) und Workflow (Ausführungs-Nodes)
- **13 Workflow-Node-Typen** existieren (`wf-input`, `wf-initialize`, `wf-strategist`, `wf-critic`, `wf-optimizer`, `wf-moderator`, `wf-fact-checker`, `wf-analyst`, `wf-creative`, `wf-user-injection`, `wf-gate`, `wf-tone-profile`, `wf-agent`)
- **Alle benötigten Agent-Core-Module** existieren bereits:
  - `analyst-default`, `creative-thinker-default`, `critic-*`, `devils-advocate-default`
  - `ethicist-default`, `expert-reviewer-default`, `fact-checker-default`, `mediator-default`
  - `moderator-*`, `optimizer-*`, `steel-manner-default`, `strategist-*`
  - `synthesizer-default`, `troll-default`
- **Kein Phasen-Konzept** vorhanden — Runden sind das einzige Strukturierungsmittel
- **Backend** `WorkflowDefinition` mit flachen `nodes`/`edges`-Listen, keine Parent-Child-Beziehung

## 5-Phasen-Modell (Referenz)

| Phase | Rollen |
|-------|--------|
| Phase 1: Problem Framing | Analyst, Creative Thinker, Socratic Questioner |
| Phase 2: Position Building | Strategist, Expert Reviewer, Steel-manner |
| Phase 3: Stress Testing | Devil's Advocate, Fact Checker, Troll (mit Tactic Ledger) |
| Phase 4: Integration | Mediator, Ethicist, Synthesizer |
| Phase 5: Closure | Moderator, Critic, Optimizer |

## Erweiterungen

### A) Neue Canvas-Workflow-Nodes (8 Stück)

Für jede dieser Rollen, die bereits als Agent-Core-Modul existiert aber noch keinen Canvas-Node-Typ hat:

| Node-Typ | Agent Core Modul | Icon | Farbe |
|----------|-----------------|------|-------|
| `wf-socratic-questioner` | (neu anzulegen) | ❓ | #8b5cf6 (purple) |
| `wf-expert-reviewer` | `expert-reviewer-default` | 🔬 | #06b6d4 (cyan) |
| `wf-steel-manner` | `steel-manner-default` | 🛡️ | #10b981 (green) |
| `wf-devils-advocate` | `devils-advocate-default` | 👿 | #ef4444 (red) |
| `wf-troll` | `troll-default` | 🤡 | #f97316 (orange) |
| `wf-mediator` | `mediator-default` | 🤝 | #3b82f6 (blue) |
| `wf-ethicist` | `ethicist-default` | ⚖️ | #14b8a6 (teal) |
| `wf-synthesizer` | `synthesizer-default` | 🔗 | #a855f7 (violet) |

Jeder Node-Typ bekommt:
- Svelte-Component (analog `AnalystNode.svelte` etc.)
- Registry-Eintrag in `registerAll.js`
- Eintrag in `WORKFLOW_CONNECTION_RULES` in `validation.js`
- Eintrag in `AGENT_NODE_TYPES` / `NODE_TYPE_LABELS` in `WorkflowNodeForm.svelte`

### B) Phase-Container (`wf-phase`)

Neuer Node-Typ, der als Container für eine Gruppe von Workflow-Nodes fungiert.

**Visuell:**
- Farbiger Kasten mit Header (Phasenname, Beschreibung)
- Enthält andere Workflow-Nodes innerhalb seiner Bounding-Box
- `sequential`-Edges zwischen Phasen-Containern = Phasenübergang
- Optional `wf-gate` zwischen Phasen

**ELK-Layout:**
- Nutzt das bestehende hierarchische Layout (nutzt bereits `round_container_N` für Runden zur Laufzeit)
- Phase-Container wird als ELK-Parent-Knoten registriert
- Enthaltene Nodes sind Children

**Inspector (PhaseForm.svelte):**
- Phasenname, Beschreibung
- Zugewiesene Rollen (Multi-Select aus vorhandenen Agent Cores)
- Max-Runden pro Phase
- Übergangstyp (sequential | gate | consensus)

**Backend-Erweiterung:**
- `WorkflowDefinition.nodes` optional um `parent_id`-Feld erweitern
- Oder `phase_config` als zusätzlicher Dict im `WorkflowDefinition`-Model

### C) Agent-Core-Modul "Socratic Questioner"

Einzige noch fehlende Rolle. Neues Modul unter `modules/agent-cores/socratic-questioner-default/`.

## Umsetzungsreihenfolge

1. Neue Canvas-Nodes (8 Typen) — schnell, da reine Kopie existierender Nodes
2. Socratic Questioner Agent-Core-Modul
3. Phase-Container (`wf-phase`) — Node, Registry, Inspector-Form
4. Backend: Phasen-Modell-Erweiterung
5. ELK-Integration für Phase-Container-Layout
