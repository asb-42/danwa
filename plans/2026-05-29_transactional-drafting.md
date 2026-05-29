# Transactional Drafting — Implementation Plan

## Übersicht

Neues Workflow-Template `transactional_drafting` mit erweitertem Node-Set (Builder, Pragmatist), neuen Edge-Typen (`builds_upon`, `validates`, `decision`), strukturierten Pydantic-Outputs und eigenem Prompt-Set. Ersetzt/erweitert nicht die Standard-Debate.

## Phase 1 — Domain Model (Backend)

### 1.1 RoleTypes ergänzen

**Datei:** `backend/blueprints/repo_roles.py` (seed) + `backend/blueprints/models.py` (keine Änderung nötig, da `category` bereits `Literal["functional", "formative"]`)

RoleType `builder`:
- id: `builder`, name: `Builder`, category: `functional`, icon: `🔨`, color: `#16a34a` (grün)

RoleType `pragmatist`:
- id: `pragmatist`, name: `Pragmatist`, category: `functional`, icon: `⚖️`, color: `#6366f1` (indigo)

→ Seed in `scripts/seed_templates.py` oder `backend/blueprints/repo_roles.py` Register-Routine.

### 1.2 WORKFLOW_NODE_TYPES erweitern

**Datei:** `backend/blueprints/workflow_models.py` ~Line 26

`"wf-builder"`, `"wf-pragmatist"` zu `WORKFLOW_NODE_TYPES` und `AGENT_NODE_TYPES` hinzufügen.

### 1.3 WORKFLOW_EDGE_TYPES erweitern

**Datei:** `backend/blueprints/workflow_models.py` ~Line 146

```python
WORKFLOW_EDGE_TYPES: list[str] = [
    "sequential", "conditional", "interjection", "feedback",
    "injects_config", "builds_upon", "validates", "decision",
]
```

### 1.4 Pydantic-Modelle

**Datei:** `backend/models/transactional.py` (neu)

```python
# CriticItem, BuildResponse, BuilderOutput,
# PragmatistEvaluation, PragmatistOutput
# (alle mit Pydantic V2, Field-Validierung, Literal-Enums)
```

### 1.5 WorkflowState erweitern

**Datei:** `backend/workflow/workflow_state.py`

Neue Keys in `WorkflowState` (optional, `total=False`):
- `zero_draft: Optional[str]`
- `critic_items: list[CriticItem]` (mit `Annotated[..., operator.add]` für Akkumulation)
- `build_responses: list[BuildResponse]`
- `pragmatist_output: Optional[PragmatistOutput]`
- `draft_version: int`
- `constructivity_score: float`

---

## Phase 2 — Prompt-Architektur

### 2.1 Prompt-Templates registrieren

Drei neue Prompt-Varianten in der Prompt-DB / im PromptService registrieren:

1. `critic_structured` — für CriticNode im transactional_drafting: JSON-Output `{ "critic_items": [...] }`
2. `builder_constructor` — für BuilderNode: JSON-Output `{ "build_responses": [...], "global_revision": "..." }`
3. `pragmatist_reality_filter` — für PragmatistNode: JSON-Output `{ "evaluations": [...], "reality_score": ..., "blocking_concerns": [...] }`

**Datei:** Prompt-Definitionen entweder als JSON-Config oder via `backend/services/prompt_service.py` Register-Methode.

Diese Varianten werden im Template `transactional_drafting` via `resolved_config.workflow_variant` zugewiesen (keine Änderung an `prompt_service.py` nötig, da `assemble_prompt` bereits `workflow_variant` unterstützt).

---

## Phase 3 — Node-Implementierungen (Backend)

### 3.1 BuilderNode

**Datei:** `backend/workflow/nodes/builder_nodes.py` (neu)

- Factory: `builder_node_factory(node_id, resolved_config)`
- Liest: `state["critic_items"]`, `state["zero_draft"]`, `state["pragmatist_output"]` (im Loop)
- Prompt: `builder_constructor`
- LLM-Call → Parse JSON → `BuilderOutput`
- Berechnet: `constructivity_score = len(build_responses) / len(critic_items)` (oder 1.0)
- Retry: max 3 Versuche bei JSON-Parse-Fehler
- Schreibt: `state["build_responses"]`, `state["constructivity_score"]`
- Audit: `event_type="builder_iteration"` mit `draft_version, constructivity_score`

### 3.2 PragmatistNode

**Datei:** `backend/workflow/nodes/pragmatist_nodes.py` (neu)

- Factory: `pragmatist_node_factory(node_id, resolved_config)`
- Liest: `state["build_responses"]`
- Prompt: `pragmatist_reality_filter`
- LLM-Call → Parse JSON → `PragmatistOutput`
- Schreibt: `state["pragmatist_output"]`
- Audit: `event_type="pragmatist_evaluation"` mit `reality_score, verdict`

### 3.3 ModeratorNode — Conditional Routing für Transactional Drafting

**Datei:** `backend/workflow/nodes/moderator_nodes.py`

Neue Factory oder erweiterte `moderator_node_factory`:
- Liest `state["pragmatist_output"]`
- Wenn `reality_score >= 0.6` und keine `blocking_concerns` → `state["consensus_result"] = {"verdict": "approved"}`
- Sonst → `state["consensus_result"] = {"verdict": "revision_required", "concerns": blocking_concerns}` + `state["draft_version"] += 1`
- Bedingte Kante: `approved` → END, `revision_required` → return_to_builder (via `decision` edge)

Alternative: Transactional Drafting verwendet `gate_node_factory` als Moderator-Ersatz mit Condition `state.get("pragmatist_output", {}).get("reality_score", 0) >= 0.6 and not state.get("pragmatist_output", {}).get("blocking_concerns", [])`.

### 3.4 WorkflowCompiler — Neue Edge-Typen

**Datei:** `backend/workflow/workflow_compiler.py`

In `_build_graph()`:
- `builds_upon`: add_edge(critic → builder), State-Transformation via `_inject_critic_items`-Wrapper
- `validates`: add_edge(builder → pragmatist)
- `decision`: bedingte Kante pragmatist → moderator, mit `route_decision()`-Router:
  - Checkt `state.get("consensus_result", {}).get("verdict")`
  - `"approved"` → END
  - `"revision_required"` → Loop zurück zu BuilderNode

### 3.5 Workflow-Router

**Datei:** `backend/workflow/workflow_routers.py` (neu oder erweitert)

`route_decision(state)`:
- Liest `state["consensus_result"]["verdict"]`
- Returns `"approved"` oder `"return_to_builder"`
- Loop-Detection: wenn `state["draft_version"] >= 5` → `"construction_deadlock"` → END mit Fehler

---

## Phase 4 — Workflow-Template

### 4.1 Template JSON

**Datei:** `templates/transactional_drafting.json` (neu)

```json
{
  "id": "tpl-transactional-drafting",
  "name": "Transactional Drafting",
  "template_data": {
    "nodes": [
      { "id": "input-1", "type": "wf-input", "label": "Case Input" },
      { "id": "init-1", "type": "wf-initialize", "label": "Initialize" },
      { "id": "strategist-1", "type": "wf-strategist", "label": "Zero Draft", "config": { "role": "strategist", "workflow_variant": "transactional_drafting" } },
      { "id": "critic-1", "type": "wf-critic", "label": "Structured Critic", "config": { "role": "critic", "workflow_variant": "critic_structured" } },
      { "id": "builder-1", "type": "wf-builder", "label": "Builder", "config": { "role": "builder", "workflow_variant": "builder_constructor" } },
      { "id": "pragmatist-1", "type": "wf-pragmatist", "label": "Pragmatist", "config": { "role": "pragmatist", "workflow_variant": "pragmatist_reality_filter" } },
      { "id": "moderator-1", "type": "wf-moderator", "label": "Approval Gate" }
    ],
    "edges": [
      { "id": "e1", "source": "input-1", "target": "init-1", "type": "sequential" },
      { "id": "e2", "source": "init-1", "target": "strategist-1", "type": "sequential" },
      { "id": "e3", "source": "strategist-1", "target": "critic-1", "type": "sequential" },
      { "id": "e4", "source": "critic-1", "target": "builder-1", "type": "builds_upon", "label": "builds_upon" },
      { "id": "e5", "source": "builder-1", "target": "pragmatist-1", "type": "validates", "label": "validates" },
      { "id": "e6", "source": "pragmatist-1", "target": "moderator-1", "type": "decision", "label": "decision" },
      { "id": "e7", "source": "moderator-1", "target": "builder-1", "type": "feedback", "label": "revision" }
    ],
    "entry_point": "input-1",
    "termination_conditions": [
      { "type": "consensus_reached", "value": 0.6, "description": "Reality score threshold" },
      { "type": "max_rounds", "value": 5, "description": "Max drafting iterations" }
    ]
  },
  "is_system": true
}
```

---

## Phase 5 — DebateArtifact & Audit-Erweiterungen

### 5.1 DebateArtifact

**Datei:** `backend/models/artifact.py`

Neue Felder in `DebateArtifact`:
- `constructivity_score: float = 0.0`
- `draft_versions: int = 0`
- `critic_item_count: int = 0`
- `build_response_count: int = 0`
- `pragmatist_reality_score: float = 0.0`

### 5.2 Audit-Log

Neue Event-Typen in AuditWriter:
- `"builder_iteration"` — logged in BuilderNode
- `"pragmatist_evaluation"` — logged in PragmatistNode

Keine Schema-Änderung nötig, `event_type` ist freier String.

### 5.3 Report-Generator

**Datei:** `backend/workflow/report_generator.py`

Neues Kapitel „Konstruktionsprotokoll":
- Tabelle: CriticItem → BuildResponse → PragmatistEvaluation (3 Spalten)
- Farbcodierung: Grün=accept, Orange=revise, Rot=reject
- Timeline bei `draft_versions > 1`

---

## Phase 6 — Frontend

### 6.1 Registry

**Datei:** `frontend/src/lib/blueprint/registerAll.js`

Neue Node-Typen registrieren:
| Type | Component | Icon | Label | Category |
|------|-----------|------|-------|----------|
| `wf-builder` | BuilderNode | 🔨 | blueprint.palette.wfBuilder | workflow |
| `wf-pragmatist` | PragmatistNode | ⚖️ | blueprint.palette.wfPragmatist | workflow |

Neue Edge-Typen registrieren:
| Type | Component | Category |
|------|-----------|----------|
| `builds_upon` | BuildsUponEdge | control_flow |
| `validates` | ValidatesEdge | control_flow |
| `decision` | DecisionEdge | control_flow |

### 6.2 Node-Komponenten

**Datei:** `frontend/src/components/blueprint/nodes/BuilderNode.svelte` (neu)
- Icon: Hammer 🔨, Farbe: Grün (#16a34a)
- Ports: 1 Input (von Critic), 1 Output (zu Pragmatist)
- Inspector: Constructivity-Score-Balken (rot < 0.5)

**Datei:** `frontend/src/components/blueprint/nodes/PragmatistNode.svelte` (neu)
- Icon: Waage ⚖️, Farbe: Indigo (#6366f1)
- Ports: 1 Input (von Builder), 2 Outputs (zu Moderator: approved / return)
- Inspector: reality_score als große Zahl, blocking_concerns als Warn-Boxen

### 6.3 Edge-Komponenten

**Datei:** `frontend/src/components/blueprint/edges/BuildsUponEdge.svelte` (neu)
- Gestrichelt, Grün, Label: "builds_upon"

**Datei:** `frontend/src/components/blueprint/edges/ValidatesEdge.svelte` (neu)
- Durchgezogen, Grau-Blau, Label: "validates"

**Datei:** `frontend/src/components/blueprint/edges/DecisionEdge.svelte` (neu)
- Doppelte Linie, Farbe dynamisch (approved=Grün, return=Orange), Label: "decision"

### 6.4 Palette

**Datei:** `frontend/src/components/blueprint/Palette.svelte`

Kategorie „Transactional Roles" hinzufügen (neben „Core Roles", „Global Config").

### 6.5 Inspector-Erweiterungen

**Datei:** CriticNode-Inspector — Badge „Structured Output Mode" wenn workflow_variant=critic_structured

**Datei:** BuilderNode-Inspector — Constructivity-Score-Balken + Warnung

**Datei:** PragmatistNode-Inspector — reality_score + blocking_concerns

### 6.6 Canvas-To-Workflow

**Datei:** `backend/blueprints/canvas_to_workflow.py`

Neue Edge-Typen `builds_upon`, `validates`, `decision` werden bereits als Canvas-Edges durchgereicht (keine Änderung nötig, da generischer Canvas-Edge-Mapper).

### 6.7 Workflow Execution — Frontend Edge Types

**Datei:** `frontend/src/components/workflow/WorkflowCanvas.svelte`

Neue Runtime-Edge-Typen registrieren:
```javascript
const edgeTypes = {
    flow: FlowEdge, feedback: FeedbackEdge,
    user_request: UserEdge, user_response: UserEdge, oob: OOBEdge,
    builds_upon: BuildsUponEdge,
    validates: ValidatesEdge,
    decision: DecisionEdge,
};
```

---

## Phase 7 — Tests

### Neue Testdatei

**Datei:** `tests/backend/test_transactional_drafting.py`

Testfälle:
1. **CriticItem JSON-Parsing**: LLM-Output → valid `CriticItem` → Pydantic-Validierung
2. **BuildResponse JSON-Parsing**: LLM-Output → valid `BuildResponse` → Pydantic
3. **PragmatistOutput JSON-Parsing**: LLM-Output → valid `PragmatistOutput` → Pydantic
4. **Constructivity-Score-Berechnung**: `len(build_responses) / len(critic_items)` → korrekter Float
5. **Loop-Detection**: `draft_version >= 5` → `termination_reason: construction_deadlock`
6. **Approval Gate**: `reality_score=0.8, no concerns` → `verdict: approved`
7. **Revision Loop**: `reality_score=0.4` → `verdict: revision_required`
8. **Template-Isolation**: Template `standard_debate` bleibt unverändert
9. **Moderator-Pflichtfelder**: `revision_note` required wenn `verdict != accept`

---

## Datei-Manifest

| Datei | Aktion |
|-------|--------|
| `backend/models/transactional.py` | **NEU** — Pydantic-Modelle |
| `backend/workflow/nodes/builder_nodes.py` | **NEU** — BuilderNode-Factory |
| `backend/workflow/nodes/pragmatist_nodes.py` | **NEU** — PragmatistNode-Factory |
| `backend/workflow/workflow_routers.py` | **NEU** — `route_decision()` |
| `templates/transactional_drafting.json` | **NEU** — Template-Definition |
| `frontend/src/components/blueprint/nodes/BuilderNode.svelte` | **NEU** |
| `frontend/src/components/blueprint/nodes/PragmatistNode.svelte` | **NEU** |
| `frontend/src/components/blueprint/edges/BuildsUponEdge.svelte` | **NEU** |
| `frontend/src/components/blueprint/edges/ValidatesEdge.svelte` | **NEU** |
| `frontend/src/components/blueprint/edges/DecisionEdge.svelte` | **NEU** |
| `tests/backend/test_transactional_drafting.py` | **NEU** |
| `backend/blueprints/workflow_models.py` | **ÄNDERN** — Edge-Typen + Node-Typen |
| `backend/workflow/workflow_state.py` | **ÄNDERN** — Neue State-Keys |
| `backend/workflow/workflow_compiler.py` | **ÄNDERN** — Neue Edge-Typen kompilieren |
| `backend/workflow/nodes/moderator_nodes.py` | **ÄNDERN** — Conditional Routing |
| `backend/models/artifact.py` | **ÄNDERN** — Neue Felder |
| `backend/workflow/report_generator.py` | **ÄNDERN** — Konstruktionsprotokoll |
| `backend/blueprints/repo_roles.py` | **ÄNDERN** — Seed builder/pragmatist |
| `frontend/src/lib/blueprint/registerAll.js` | **ÄNDERN** — Registry-Einträge |
| `frontend/src/components/blueprint/Palette.svelte` | **ÄNDERN** — Neue Kategorie |
| `frontend/src/components/workflow/WorkflowCanvas.svelte` | **ÄNDERN** — Neue Edge-Typen |

---

## Akzeptanzkriterien (aus den Arbeitsanweisungen)

- [ ] Nutzer kann Template „Transactional Drafting" im Workflow Builder auswählen
- [ ] Critic produziert valides JSON `CriticItem[]` (kein Freitext)
- [ ] Builder produziert für jedes CriticItem mindestens option_a + option_b
- [ ] Pragmatist bewertet jede Option mit feasibility + process_risk
- [ ] `reality_score < 0.6` oder `blocking_concerns vorhanden` → Loop zu Builder
- [ ] `constructivity_score` in Audit-Log + DebateArtifact
- [ ] Inspector zeigt Metriken für Builder + Pragmatist in Echtzeit
- [ ] Report enthält Konstruktionsprotokoll als farbcodierte Tabelle
- [ ] Loop-Detection: max 5 Iterationen → `construction_deadlock`
- [ ] Standard-Debate bleibt unbeeinflusst
