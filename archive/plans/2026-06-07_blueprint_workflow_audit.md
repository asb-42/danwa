# Analyse: Blueprint / Workflow Canvas / LangGraph & Transactional Drafting

Stand: `main` @ `0b1169a` (nach Merge `fix/ui-ux`). Audit nur — keine Code-Änderungen vorgenommen.

---

## 1. Architektur-Übersicht

### 1.1 Komponenten-Map

| Layer | Pfad | Zeilen | Rolle |
|-------|------|--------|-------|
| **Frontend Canvas** | `frontend/src/components/blueprint/BlueprintCanvas.svelte` | 731 | SvelteFlow-Wrapper, DnD, Connection-Validation |
| **Frontend Store** | `frontend/src/lib/blueprint/store.svelte.js` | 311 | Svelte-5-Runes-Singleton für Nodes/Edges |
| **Frontend View** | `frontend/src/views/BlueprintCanvasView.svelte` | — | Bindeglied zur Palette, Inspector, Save-Dialoge |
| **Frontend Mode** | `frontend/src/lib/blueprint/{validation,dnd,edgeWiring,layout,registerAll,registry}.js` | 8 Dateien | Mode-Switching, ELK-Layout, Backend-Sync |
| **Workflow Frontend** | `frontend/src/lib/workflow/{store,graphReducer,runtimeReducer,mapper,oob,layout,workflowSSE}.js` | 7 Dateien | Svelte 5 Runes + SSE für Live-Execution |
| **Backend Compiler** | `backend/workflow/workflow_compiler.py` | 535 | `WorkflowDefinition` → `langgraph.StateGraph` |
| **Backend Runner** | `backend/workflow/workflow_runner.py` | 755 | Async-Background-Loop, Artifact-Building, Pause/Resume |
| **Backend Nodes** | `backend/workflow/nodes/{agent,builder,pragmatist,angels_advocate,moderator,system}_nodes.py` | 6 Dateien / 2381 Zeilen | LangGraph-Node-Factories |
| **Backend Routers** | `backend/workflow/workflow_routers.py` | 161 | Conditional-Edge-Router (Feedback/Decision/Gate) |
| **Backend State** | `backend/workflow/{state,workflow_state,state_snapshot}.py` | — | TypedDict-State, SQLite-Snapshots |
| **Backend Audit** | `backend/workflow/{audit_logger,immutability}.py` | — | Append-only Audit-Trail |
| **Backend Templates** | `templates/*.json` (DEPRECATED) + `modules/workflows/*` (neu) | — | Workflow-Vorlagen |

### 1.2 LangGraph vs. Custom

Echtes **LangGraph** wird genutzt:
- `langgraph.graph.StateGraph` (import in `workflow_compiler.py:13`, `debate_graph.py:17`, `hitl/graph.py:17`)
- `graph.ainvoke(initial_state, config={"recursion_limit": N})` (`workflow_runner.py:153`)
- `add_conditional_edges(node_id, router_fn, mapping_dict)` für Feedback/Decision/Gate
- `Annotated[..., operator.add]` Reducer für List-Accumulatoren (`workflow_state.py:58-64`)

Kein custom "Graph" — die `WorkflowDefinition` ist ein dünner Wrapper, der via `WorkflowCompiler` zu einer echten LangGraph `StateGraph` kompiliert wird.

### 1.3 Persistenz-Architektur

Alle Persistenz läuft über **SQLite** mit der gleichen DB-Datei `data/blueprints.db`:
- `blueprints.repository.BlueprintRepository` — Blueprints, Templates, Profiles
- `state_snapshot.StateSnapshotStore` — State nach jedem Node (für Replay/Resume)
- `audit_logger.AuditLogger` — Append-only Audit-Trail
- Direkter sqlite3 in `pragmatist_nodes.py:303` — `build_response_provenance`-Tabelle (ad-hoc)

Drei **separat gepersistierte** Repräsentationen desselben Workflows:
1. `audit_log` (Append-only Eventlog)
2. `state_snapshots` (Full-State nach jedem Node)
3. `build_response_provenance` (Direkter sqlite3-Bypass)

Keine Migration-Nummer für `build_response_provenance` — die Tabelle wird on-the-fly in `_save_provenance_batch` erzeugt (`pragmatist_nodes.py:307`).

---

## 2. Transactional Drafting Mode

### 2.1 Was es laut Code sein soll

Laut Docstrings und Pydantic-Modellen (`backend/models/transactional.py:1-202`):

```
Strategist (Zero-Draft) → Critic (CriticItem[]) → Angel's Advocate (PreservedElement[])
→ Builder (BuildResponse[] + Provenance) → Pragmatist (PragmatistOutput + verdict)
→ Moderator (Approval-Gate mit Decision-Router)
```

- **8 Knoten-Typen**: `wf-strategist`, `wf-critic`, `wf-angels-advocate`, `wf-builder`, `wf-pragmatist`, `wf-moderator`, `wf-input`, `wf-initialize`
- **2 Decision-Edges vom Moderator**: `approved` (→ END) und `revision_required` (→ Builder für Loop)
- **Magic-String** überall: `state.get("workflow_template") == "transactional_drafting"` (5 Stellen)
- **Pydantic-Schemas**: `CriticItem`, `BuilderOutput`/`BuildResponse`/`Provenance`, `PragmatistOutput`/`PragmatistEvaluation`, `AngelsAdvocateOutput`/`PreservedElement`

### 2.2 Datenfluss

1. **Template-Lookup**: `templates/transactional_drafting.json` (113 Zeilen) hat `tpl-transactional-drafting`-ID
2. **Compilation**: `WorkflowCompiler` baut StateGraph mit 8 Knoten, 9 Edges, Decision-Mapping
3. **Execution**: `run_workflow_background` ruft `graph.ainvoke()` mit `recursion_limit = num_nodes * (max_rounds+1) * 2 + 20`
4. **Node-Lifecycle** (alle Knoten folgen diesem Muster):
   - `await publish_async("node.start", ...)` SSE
   - LLM-Call mit JSON-Schema-Injection + json_repair-Fallback (3 Retries)
   - Provenance-Attachment
   - `await publish_async("node.complete", ...)` SSE
   - `audit_logger.log_node_execution()` → SQLite
5. **Decision-Routing**: Nach Moderator wählt `route_decision` einen von 3 Strings: `approved` | `return_to_builder` | `construction_deadlock`
6. **Loop-Detection**: `draft_version >= 5` oder `current_round > effective_max` → `construction_deadlock` → END
7. **Artifact-Building**: Spezielle Fast-Path in `_build_artifact_from_state` (`workflow_runner.py:565`) — konstruiert `DebateArtifact` mit Provenance-Marginalia
8. **Print-Template**: `PrintTemplate.TRANSACTIONAL_DRAFTING` rendert spezielles HTML-Layout

### 2.3 ⛔ KRITISCH: Feature ist nicht erreichbar

**Befund**: Der gesamte Transactional Drafting Code ist **Dead Code** im aktuellen Runtime-Pfad.

| Evidenz | Detail |
|---------|--------|
| `templates/DEPRECATED.txt:1-9` | Verzeichnis am 2026-05-14 als deprecated markiert, "kann zu späterem Zeitpunkt gelöscht werden" |
| `modules/workflows/` | Enthält 9 Workflow-Templates (`tpl-5-phase-debate`, `tpl-dialectic-debate`, `tpl-kantian-analysis`, `tpl-interview`, `tpl-mediation`, `tpl-streitgespraech`, `tpl-standard-debate`, `tpl-quick-review`, `socratic-debate`) — **kein `tpl-transactional-drafting`** |
| `grep -rn "tpl-transactional" backend/` | **Keine Treffer** — kein Loader referenziert das Template |
| `workflow_templates.py:50-67` | `list_workflow_templates` liest nur aus DB + `get_workflow_templates_from_modules()` — `templates/*.json` wird ignoriert |
| `test_transactional_drafting.py:1-551` | 42 Tests, **alle testen nur Pydantic-Modelle** (CriticItem, BuildResponse, PragmatistOutput, Verdict-Thresholds). **Kein einziger Integrationstest** für die Node-Factories, Decision-Router oder End-to-End-Flow |
| Frontend | **Kein** Verweis auf `transactional_drafting` in `frontend/src/**` |

**Impact**:
- `backend/models/transactional.py` (202 Zeilen): komplett ungenutzt
- `backend/workflow/nodes/{builder,pragmatist,angels_advocate}_nodes.py` (1041 Zeilen): komplett ungenutzt (außer von sich selbst)
- `backend/workflow/workflow_routers.py:116-161` `route_decision` (46 Zeilen): nie aufgerufen
- `backend/workflow/workflow_runner.py:565-575, 712-722`: Fast-Path-Branches nie betreten
- `backend/services/output/plugins/print_plugin.py:35, 109`: Print-Template-Enum und Selector
- Migration v31 (`critic_item_id`/`build_response_id`/`draft_version`/`constructivity_score` Audit-Spalten): keine Schreiber
- Migration v32 (`build_response_provenance`-Tabelle): wird on-the-fly in pragmatist_nodes erzeugt, aber das Modul läuft nie
- `tests/backend/test_transactional_drafting.py` (551 Zeilen): testet 0 % des Runtime-Pfads

**Wahrscheinliche Ursache**: Migration zu Modulen war unvollständig — der Designer hat den Template-JSON nicht ins `modules/workflows/`-Verzeichnis kopiert, und der Code in `templates/` wurde als deprecated markiert.

---

## 3. Bug-Inventar (priorisiert)

### CRITICAL

#### C1. ~~`eval()`-Sandbox in Gate-Conditions (`workflow_routers.py:42`, `moderator_nodes.py:270`)~~ **Fixed Sprint 28**

```python
if safe_eval.evaluate_condition(expr, state):
```

**Status**: Mit `__builtins__: {}` ist `__import__`/`open` blockiert, aber:
- State-Dict-Keys sind als Variablen verfügbar → `state["__class__"]` o.ä. injection-fähig
- Wenn `expr` aus einer DB oder User-Eingabe stammt, kann `__class__.__base__.__subclasses__()` (Python-Leak) die Sandbox umgehen
- `noqa: S307` zeigt, dass der Linter warnt — der Author kennt das Risiko
- **3 separate Stellen**: `route_conditional`, `_gate_node`, **kein** Schutz in `route_decision`

**Fix-Optionen**:
- AST-basiertes Whitelisting (nur `<`, `>`, `==`, `and`, `or`, `not`, Identifier)
- AST-basiertes Sandbox (`simpleeval`, `asteval` Libraries)
- Domain-spezifische DSL (z.B. `consensus > 0.6 AND round < 3`)

#### C2. State-Accumulator-Bug für `critic_items` und `build_responses`

`workflow_state.py:80-81` definiert:
```python
critic_items: Annotated[list[dict], operator.add]
build_responses: Annotated[list[dict], operator.add]
```

LangGraph wendet `operator.add` (List-Concat) an. Aber die Node-Code REPLACED die Listen:

- `agent_nodes.py:451-456`: `state_update["critic_items"] = items` (komplett überschrieben)
- `builder_nodes.py:374`: `"build_responses": [b.model_dump() for b in builder_output.build_responses]` (überschrieben)
- `pragmatist_nodes.py:288`: `"build_responses": updated_build_responses` (überschrieben)

**Konsequenz**: Bei einem Return-to-Builder-Loop:
- Iteration 1: `critic_items = [c1, c2]`, `build_responses = [b1]`
- Iteration 2: Critic generiert 3 neue Items `[c3, c4, c5]`. Builder sieht `critic_items = [c3, c4, c5]` (überschrieben — gut), generiert 3 BuildResponses `[b2, b3, b4]`.
- **ABER**: LangGraph hat den `operator.add`-Reducer. Wenn `state_update["critic_items"] = [c3, c4, c5]` zurückgegeben wird, merged LangGraph: `[c1, c2] + [c3, c4, c5] = [c1, c2, c3, c4, c5]`. Builder sieht dann ALLE 5 CriticItems.

→ Builder produziert redundante BuildResponses für bereits gelöste Items. Provenance wird inkorrekt (jede BuildResponse referenziert nur eine critic_id, aber das System vergibt `c-001` jedes Mal neu).

**Fix**: `critic_items: list[dict]` (ohne `operator.add`) ODER Code-Migration auf `state_update["critic_items"] = items` mit Annahme dass nur die neuesten relevant sind.

#### C3. ~~Decision-Mapping ignoriert `revision_required` direkt (`workflow_compiler.py:391-396`)~~ **Fixed Sprint 32**

```python
verdict_map: dict[str, str] = {}
for edge in decision_edges:
    cond = edge.condition or "approved"
    if cond in {"approved", "revision_required", "construction_deadlock"}:
        verdict_map[cond] = {
            "approved": "approved",
            "revision_required": "return_to_builder",
            "construction_deadlock": "construction_deadlock",
        }[cond]
    else:
        verdict_map[cond] = cond
        logger.warning("Custom decision edge condition '%s' …", cond)
graph.add_conditional_edges(
    node.id,
    route_decision(decision_max_rounds, verdict_map=verdict_map),
    {key: targets.get(verdict, END) for verdict, key in verdict_map.items()},
)
```

Implementierung in Sprint 32 (`workflow_routers.py` + `workflow_compiler.py`):
- `route_decision(max_rounds, verdict_map=None)` Factory nimmt jetzt ein explizites `verdict_map: dict[verdict_value, mapping_key]`. Default = Legacy-Mapping `{"approved": "approved", "revision_required": "return_to_builder"}` (backward-compatible mit allen bestehenden Templates).
- Compiler baut `verdict_map` aus den **tatsächlichen Decision-Edges** statt hardcoded. Bekannte Conditions mappen auf ihre Legacy-Schlüssel, custom conditions werden als warning geloggt und als identity-Mapping akzeptiert.
- Mapping-Lookup ohne Fallback auf `__complete__` — fehlende Targets warnen laut (`logger.warning`) statt silent zu routen.
- 11 neue Tests in `test_decision_mapping.py`:
  - 6 Router-Tests (Legacy-Default, custom verdict_map, unmapped-Fallback, Deadlock-Priorität, max-draft-versions, fehlender consensus_result)
  - 3 Compiler-Tests (Standard-Conditions, custom conditions, mixed)
  - 2 statische Guards (verdict_map-Parameter aktiv, kein `__complete__`-Fallback mehr)
- 225/225 erweiterte workflow-Tests grün, ruff clean.

#### C4. ~~`route_decision` hat `noqa: S307` für `eval` — siehe C1~~ **Fixed Sprint 28** (zusammen mit C1)

C1 und C4 waren beide Manifestationen derselben Klasse von Bugs:
`eval(expr, {"__builtins__": {}}, dict(state))` ist **kein** sicherer
Sandbox — `(1).__class__.__base__.__subclasses__()` kann den
Sandbox umgehen.  C1 (in `workflow_routers.py:42`) und C4 (in
`route_decision` an einer zweiten Stelle) wurden beide im selben
Commit (`d48d387`, Sprint 28) behoben:

* `backend/workflow/safe_eval.py` — AST-Whitelist-Evaluator
  (siehe C1 für Details).
* `route_decision` enthält heute **kein** `eval()` und **kein**
  `noqa: S307` — `grep -rn 'noqa.*S307' backend/` liefert 0 Treffer.

`route_decision` (`workflow_routers.py:236`) macht nur
`state.get(...)`-Lookups und Dict-Lookups (`verdict_map.get(...)`),
also keine User-Input-Evaluation mehr.  Die maximale Draft-Version
ist über `_resolve_max_draft_versions(state)` aus
`termination_conditions` konfigurierbar (ebenfalls Sprint 28).

Verbleibendes `eval()`/`exec()`-Risiko im Code: keines
(`grep -rn '= eval(' backend/` → 0; `asyncio.create_subprocess_exec`
ist ein eigener API-Aufruf und nicht `exec()`).

### HIGH

#### H1. ~~Modul-Singleton brechen bei Multi-Process (`interjection.py:158`)~~ **Fixed Sprint 37+38**

```python
interjection_service = InterjectionService()
```

In-Memory-Queue pro Python-Prozess. Bei `uvicorn --workers N` haben Worker A und B **separated Queues**. Ein User-Inject auf Worker A wird vom Worker B nicht gesehen.

Zusätzlich: `_pause_events`, `_cancelled_sessions`, `_session_status` in `workflow_runner.py:30-32` haben das gleiche Problem.

**Fix (4 Teil-Sprints)**: Redis-Backed Implementation (das System hat schon `RedisWorkflowState`).

- **Sprint 37 (1/3)**: `pubsub.py` + `wait_event.py` Protocol/Impls als cross-process sync primitives.
- **Sprint 37 (2/3)**: `wait_for_pause`/`wait_for_resume` Block-on-Event-Ersatz in `workflow_state.py`.
- **Sprint 37 (3/3)**: 3 Cancel/Pause-Mechanismen konsolidiert — `workflow_runner` + `debate_oob` + `_cancelled_debates` delegieren an `get_workflow_state()`. Module-Level-Singleton (`reset_*_cache()` für Tests).
- **Sprint 38 (3/3)**: Letzter Process-Local-Singleton (`hitl/api.py:_paused_debates`) ebenfalls konsolidiert über `get_workflow_state().get_hitl_pause()` / `set_hitl_pause()` / `clear_hitl_pause()`.

Verbleibender Process-Local-State: `_oob_queues` in `debate_oob.py` (Message-Queue, separate Concerns — Follow-up).

#### H2. ~~`current_draft` wird in ALLEN Agent-Nodes überschrieben (`agent_nodes.py:437, 447`)~~ **Fixed Sprint 39**

```python
existing_draft = state.get("current_draft", "")
new_draft = existing_draft + f"\n\n[{role.upper()} Round {current_round}]\n{content}"
```

Builder setzt in `builder_nodes.py:376` seinen eigenen `current_draft` (Line-Override), aber der **base agent_factory** in `agent_nodes.py` returnt `current_draft: new_draft` (angehängt). Da die `_agent_node` zuerst läuft und das Dict zurückgibt, **überschreibt** der Builder seinen custom-current_draft nicht. Im State akkumuliert `current_draft` weiter.

Konsequenz: `current_draft` wächst unendlich, wird bei 50000 chars trunkiert (`agent_nodes.py:438`), aber die Trunkierung ist **head+tail**, sodass der Anfang verloren geht.

**Fix (Sprint 39)**:

- Geteilter Helper `truncate_running_draft` in `backend/workflow/nodes/_draft_helpers.py` — Single Source of Truth für die Bound.
- **Tail-Only** statt Head+Tail: behält den letzten 50k-Chars, verwirft den Head (was bei LLM-Prompts sowieso nicht in den Context Window passt).
- Konsistenz: `agent_nodes._agent_node`, `system_nodes.interjection_node` und `legacy_nodes.run_agent_node` rufen denselben Helper — vorher hatten die letzten beiden **gar keine** Truncation.
- 13 neue Tests in `test_draft_helpers.py` (Helper-Unit-Tests + Integration-Tests an allen 3 Call-Sites).
- L2-Tests in `test_agent_node_polish.py` auf den neuen Speicherort der Konstanten geupdated.

Builder-Override-Behavior bleibt unverändert: Builder's `state_update["current_draft"] = global_revision` überschreibt weiterhin die Akkumulation in transactional flows.

#### H3. ~~`route_decision` Deadlock-Logik fehlerhaft (`workflow_routers.py:144`)~~ **Fixed Sprint 28**

```python
max_draft_versions = _resolve_max_draft_versions(state)
if draft_version >= max_draft_versions:
    return "construction_deadlock"
```

`_resolve_max_draft_versions(state)` liest `termination_conditions` nach `{"type": "max_draft_versions", "value": N}`. Default 5 für Backwards-Compat.

#### H4. ~~Magic String `"transactional_drafting"` an 5 Stellen~~ **Fixed Sprint 30**

```python
state.get("workflow_template") == WorkflowTemplate.TRANSACTIONAL_DRAFTING
```

Implementierung in Sprint 30 (`workflow_state.py` + 4 Produktionsdateien):
- Neuer :class:`backend.workflow.workflow_state.WorkflowTemplate` StrEnum mit Werten `DEBATE = "debate"`, `ACADEMIC_DEBATE = "academic_debate"`, `TRANSACTIONAL_DRAFTING = "transactional_drafting"` — identisch zu den historischen Literalen, also round-trip-kompatibel mit serialisierten State-Dicts.
- Ersetzt in: `moderator_nodes.py:81`, `agent_nodes.py:81+387`, `workflow_runner.py:565+712`, `print_plugin.py:109`. `PrintTemplate.TRANSACTIONAL_DRAFTING` (print-spezifisch) bleibt parallel bestehen, sein Wert ist per Test gegen `WorkflowTemplate.TRANSACTIONAL_DRAFTING` verriegelt.
- 5 neue Tests in `test_workflow_template_enum.py` (Enum-Werte, StrEnum-Subclass, String-Vergleich, **statischer Guard-Test** der per grep sicherstellt dass kein Produktionsfile mehr den Bare-Literal vergleicht — verhindert Regression).
- `test_agent_node_skips_current_draft_concat_for_transactional` akzeptiert nun Literal- und Enum-Form.
- 193/193 workflow-Tests grün, 171/171 erweiterte Tests grün, ruff clean.

#### H5. Provenance `_save_provenance_batch` Hardcoded DB-Pfad (`pragmatist_nodes.py:303`)

```python
db_path = Path("data/blueprints.db")
```

Hardcoded — bricht bei:
- Docker-Container mit anderem Working-Directory
- Tests mit `:memory:`-SQLite
- Multi-Environment-Configs

Andere Module nutzen `BlueprintRepository` oder den konfigurierten DB-Pfad. **Fixed Sprint 31** via `MiscRepository.save_provenance_batch()` — der Pragmatist-Node instanziiert `BlueprintRepository()` (gleiche Pattern wie `moderator_nodes.py:401-424` für Tone-Profile-Loads), der Pfad ist `BaseRepo.__init__` konfigurierbar, die Tabelle lebt in Migration v32 (nicht inline `CREATE TABLE IF NOT EXISTS`).

#### H6. ~~`interjection_node` setzt `is_paused=True` aber pausiert nicht (`system_nodes.py:300-339`)~~ **Fixed Sprint 29**

Der Lambda in `workflow_compiler.py:455-458` returnt weiterhin `"next"` — die echte Pause passiert jetzt **im Node selbst** durch blockierendes Warten auf `interjection_service.consume_blocking()`.

Implementierung in Sprint 29 (`interjection.py` + `system_nodes.py`):
- `InterjectionService.consume_blocking(session_id, node_id, timeout=300)` blockiert via per-session `asyncio.Event` (Wake-Up-Pattern) bis `submit()` einreicht.
- `submit()` setzt das Wake-Event; `consume()`/`clear()` löschen es.
- `interjection_node` versucht drei Quellen in dieser Reihenfolge: in-state `interjection_queue` → service-Queue (non-blocking) → `consume_blocking(timeout=state.get("pause_timeout"))`. Fällt auf `is_paused=True` zurück wenn Timeout feuert oder `pause_timeout=0` (default = legacy-Verhalten).
- `pause_timeout` ist ein optionales State-Feld; ohne es bleiben alle bisherigen Tests/Caller kompatibel.

Trade-off: Bei `pause_timeout > 0` blockiert der Workflow-Thread bis Antwort kommt oder Timeout feuert. Default 300s ist ein vernünftiger Kompromiss für Human-in-the-Loop; Production sollte das via Blueprint konfigurieren.

#### H7. ~~`route_feedback` Extension-Logik nicht verwendet (`workflow_routers.py:75-104`)~~ **Fixed Sprint 38 (1+2/3)**

`extension_granted` und `enable_extra_rounds` werden nur in `moderator_nodes.py:160-220` gelesen — der Extension-Flow ist **separat** vom Feedback-Router. Die zwei müssen synchron sein, sind es aber nicht.

Im Moderator (moderator_nodes.py:191-220): synchrone Polling-Loop mit `asyncio.sleep(2)` für 5 Minuten → **blockiert den ganzen Workflow-Thread**.

**Fix (2 Teil-Sprints)**:

- **Sprint 38 (1/3)** (`23ae360`): `set_extension_signal` / `wait_for_extension_signal` auf `WorkflowStateBackend` (InMemory + Redis). `moderator_nodes.py` Polling → WaitEvent (Wake-up in < 10 ms statt 2 s). `hitl/api.py:extension_decision` feuert Signal nach Debate-Save.
- **Sprint 38 (2/3)** (`5cc1bcd`): `hitl/nodes.py:extension_request_node` ebenfalls refactored (zweiter Extension-Code-Pfad). `hitl/api.py:resolve_interrupt` feuert Signal als Side-Effect — deckt den generischen `respond_to_interrupt`-Pfad ab.

Verbleibend (out-of-scope, Follow-up): 2 weitere 2 s-Pollings in `hitl/nodes.py:74-76` (HITL-pause polling, 10 min max) und `hitl/nodes.py:248` (agent query interrupt polling).

#### H8. `execution_panel.svelte:135-180`: `wf-pragmatist` Node-Type existiert nicht in `registerAll.js` Whitelist?

Tatsächlich, `registerAll.js:527` registriert `wf-pragmatist`. OK.

### MEDIUM

#### M1. ~~Workflow-Compiler Warning über Multi-Target ohne Gate (`workflow_compiler.py:475-480`)~~ **Fixed Sprint 33**

Wenn ein Knoten mehrere outgoing non_feedback-Edges hat, ohne Gate zu sein, wird der erste genommen und der Rest ignoriert. Sprint 33 appended die Warning jetzt in `CompiledWorkflow.warnings` (zusätzlich zu `logger.warning`), sodass Caller sie programmatisch sehen können.

```python
msg = (
    f"Node '{node.id}' has {len(non_feedback)} non-feedback "
    f"outgoing edges but is not a gate. Using first target "
    f"'{non_feedback[0].target}' — other targets are ignored. "
    f"Wrap in a wf-gate node or split into multiple nodes."
)
logger.warning(msg)
warnings.append(msg)  # <-- now surfaced to CompiledWorkflow.warnings
```

`_build_graph` returnt jetzt `(graph, warnings)`, der Compile-Orchestrator merged sie in `result.warnings`.

#### M2. ~~Kahn-Topological-Sort mit O(n) `pop(0)` (`workflow_compiler.py:295-308`)~~ **Fixed Sprint 33**

```python
queue: deque[str] = deque(nid for nid in node_ids if in_degree.get(nid, 0) == 0)
...
current = queue.popleft()  # O(1) statt O(n)
```

Linear-Time O(V+E) verifiziert mit 200-Knoten-Workflow-Test.

#### M3. ~~Topological-Sort ignoriert Decision-Edges vollständig (`workflow_compiler.py:288`)~~ **Fixed Sprint 41**

`WorkflowCompiler._topological_sort` schloss Decision-Edges vom
Sort aus.  Folge: ein Moderator mit Decision-Edge
`(approved) → Builder` baute KEINE Order-Beziehung zwischen
Moderator und Builder auf — der Builder konnte im statischen
`node_sequence` (für Inspector / Observability) VOR dem
Moderator auftauchen.  Die Runtime-Routing-Graph respektierte
die Decision (Moderator lief zuerst, `route_decision` wählte
das Target), aber die statische Repräsentation war falsch.

**Fix (Sprint 41)**:

* `_topological_sort` schließt jetzt nur noch
  `feedback`, `injects_config`, `interjection`,
  `builds_upon`, `validates` aus — Decision-Edges sind
  drin.
* Self-Loops (z.B. Decision-Edge `Moderator → Moderator` auf
  `revision_required`) werden separat übersprungen, damit
  Kahn's Algorithmus terminiert.
* 6 Tests in `test_decision_topological_order.py`:
  - 3 dynamische Tests (Decision-Edge-Ordering, Self-Loop,
    Decision-zu-`__end__`).
  - 1 Test dass Feedback-Edges weiterhin excluded sind.
  - 2 statische Code-Contract-Checks (Decision in der
    Exclusion-Liste, Feedback in der Exclusion-Liste).

```python
if edge.type not in ("feedback", "injects_config", "decision"):
    adj[edge.source].append(edge.target)
```

Decision-Edges werden aus der Topo-Sort ausgeschlossen. Moderator hat nur decision-edges → wird isoliert. Der Code fängt das ab (Zeile 311-313: "Add any nodes not reached"), aber die Reihenfolge ist beliebig.

#### M4. ~~`agent_node_factory` ohne Tone-Profile-Source crasht nicht, schweigt aber (`agent_nodes.py:184-209`)~~ **Fixed Sprint 34**

```python
tone_profile_error: str | None = None
if tone_profile_source_node_id:
    ...
    if profile_data:
        try:
            ...
        except Exception as exc:
            tone_profile_error = f"{type(exc).__name__}: {exc}"
            logger.warning(...)
    else:
        # Source configured but produced no profile_data
        tone_profile_error = f"tone_profile_source_node_id '{X}' produced no profile_data..."
        logger.warning(...)
...
audit_metadata["tone_profile_error"] = tone_profile_error
```

Sprint 34 erfasst den Fehler explizit in `tone_profile_error` und propagiert ihn in `audit_metadata['tone_profile_error']`. Zusätzlich wird der Fall "Source konfiguriert aber kein profile_data in state" erkannt (vorher silent — kein Profile angewendet, kein Hinweis).

#### M5. ~~`agent_nodes.py:336` `tokens_used = len(content.split())` als Fallback~~ **Fixed Sprint 34**

```python
def _estimate_tokens(content: str) -> int:
    if not content:
        return 0
    return max(1, len(content) // 4)
```

Sprint 34 nutzt die Industrie-Regel `1 token ≈ 4 characters` (tiktoken/OpenAI cookbook) statt Whitespace-Word-Count. 3 Fallback-Stellen umgestellt (LLM-Failure, tokens_out=0, optional-search-path). Verifiziert: 100 chars → 25 tokens (war: 50 words bei "a "*50, jetzt: 25).

#### M6. ~~Frontend `canvasStore` Singleton-Problem (`store.svelte.js:311`)~~ **Fixed Sprint 44**

```javascript
export const canvasStore = new BlueprintCanvasStore();
```

Wenn `BlueprintCanvasView.svelte` lazy-loaded wird und der User zwischen Routes wechselt, kann eine Race-Condition entstehen: Beim Verlassen der View wird der State nicht zurückgesetzt, beim Wiedereintritt ist der alte State noch da. Aktuell wird `reset()` nirgends automatisch aufgerufen.

**Fixed Sprint 44**: Added a Svelte 5 `$effect(() => { return () => canvasStore.reset(); })` in `BlueprintCanvasView.svelte` so the cleanup runs on view unmount. Also extended `canvasStore.reset()` to clear `isLoading` (the original reset left a stuck-loading state if the user navigated away mid-load). 6 new regression tests: 3 in `store.test.js` verify `reset()` clears every field including `isLoading`; 3 in `canvasViewCleanup.test.js` statically assert the `$effect`-cleanup pattern + audit M6 reference is present. All 114 frontend unit tests pass; production build succeeds.

#### M7. ~~`loadFromLayout` ohne Dirty-Check (`store.svelte.js:188-250`)~~ **Fixed Sprint 45**

Lädt neuen Layout-State ohne zu prüfen, ob `isDirty=true`. User-Edits werden silent verworfen.

**Fixed Sprint 45**: Added `hasUnsavedChanges` getter on the store. Added three dirty-check guard wrappers in `BlueprintCanvasView.svelte` (`loadLayoutWithGuard`, `loadWorkflowWithGuard`, `handleInstantiatedWithGuard`) that queue the requested load into a `pendingLoad` state when `isDirty` is true. A reusable `<ConfirmDialog>` (`common.unsavedChanges` i18n key) is shown; on confirm the queued action runs, on cancel the canvas state is preserved. All three load paths now go through the guards: route-driven `$effect`, gallery `handleLoadLayout`, and `TemplateInstantiateModal.onSuccess`. 12 new tests: 5 unit tests for `hasUnsavedChanges` getter and 7 static regression tests in `unsavedChangesGuard.test.js` verifying dialog wiring + 3 call sites + audit reference. All 126 frontend unit tests pass; production build succeeds.

#### M8. ~~`BlueprintCanvas.svelte:445-450` `setTimeout(100ms)` für `flow.fitView()`~~ **Fixed Sprint 46**

```javascript
setTimeout(() => flow.fitView({ padding: 0.3 }), 100);
```

Magic-Number 100ms — kann auf langsamer Hardware zu früh sein. Besser: `requestAnimationFrame` × 2 oder `ResizeObserver`.

**Fixed Sprint 46**: Replaced the manual `setTimeout(() => flow.fitView({ padding: 0.3 }), 100)` in the bridge's onready callback with SvelteFlow's built-in `fitView` + `fitViewOptions={{ padding: 0.3 }}` props on the `<SvelteFlow>` element. SvelteFlow's internal handler waits for `nodesInitialized` (every node measured) rather than guessing a delay, so the initial viewport is always correct on slow hardware. Bridge now only exposes the flow instance for `screenToFlowPosition` on drops. 6 new static regression tests in `fitView.test.js` verify: no `setTimeout(fitView)` anywhere, `fitView` prop present, `padding: 0.3` preserved, audit reference present, bridge doesn't call `flow.fitView` itself, bridge still fires `onready` once via `onMount`. All 132 frontend unit tests pass; production build succeeds.

#### M9. ~~`_save_provenance_batch` schließt Connection nicht im Error-Pfad (`pragmatist_nodes.py:349-352`)~~ **Fixed Sprint 31**

`conn` ist im `try` definiert — wenn `sqlite3.connect` selbst failed, ist `conn` undefined und `conn.close()` schmeißt `UnboundLocalError`. Der innere `try/except` fängt das, aber es ist hässlich.

Sprint 31 hat die Provenance-Persistenz in `MiscRepository.save_provenance_batch()` zentralisiert — der nutzt `with self._connect() as conn:` (auto-close via context manager), und `pragmatist_nodes._save_provenance_batch()` ist nur noch ein dünner Wrapper. Damit ist das UnboundLocal-Risiko eliminiert.

#### M10. ~~`audit_logger.py` und `state_snapshot.py` nutzen separate `sqlite3.connect`-Aufrufe~~ **Fixed Sprint 43**

Jeder Audit-Eintrag und Snapshot öffnet/schließt eine neue SQLite-Connection. Bei 100 Audit-Events = 100 Connect-Overhead. Sollte Connection-Pool nutzen.

**Fixed Sprint 43**: Both `AuditLogger` and `StateSnapshotStore` now cache a single `sqlite3.Connection` per instance via `_get_conn()`. First call lazily opens the connection with `check_same_thread=False` + `timeout=30.0` and enables WAL journal mode (best-effort). All public methods use the cached connection inside a `threading.RLock` for safe concurrent access. `close()` releases the connection (for tests/shutdown). 100 writes now = 1 `sqlite3.connect` call. 10 regression tests in `test_connection_reuse.py` verify single-connection behaviour, WAL mode, `close()` release/reopen, and 8-thread × 25-write concurrency (200 rows persist). Public API unchanged.

#### M11. ~~Workflow-Runner ignoriert `state.get("extension_granted")` von früheren Iterationen (`moderator_nodes.py:162-180`)~~ **Fixed Sprint 42**

`extension_granted` wird im State geprüft, aber wenn der Moderator **nach** dem Decision-Router läuft und der Router `approved` returned, hat `extension_granted` keine Wirkung auf den Router-Output.

**Fixed Sprint 42**: `route_decision` (in `backend/workflow/workflow_routers.py`) terminates with `construction_deadlock` on `current_round > effective_max`, ignoring `extension_granted`. `route_feedback` (used for feedback-loop edges) already honours the flag — it allows up to `max_rounds + 2` rounds when `enable_extra_rounds` is set and `extension_granted` is True. `route_decision` had the same gap, so the user-granted extension was silently discarded: workflow returned to the builder for one more round (verdict=revision_required), but on the second extension round the decision router terminated with `construction_deadlock` instead of routing to the verdict target. Fix: when `enable_extra_rounds`, `extension_granted is True`, and `current_round` is in `(effective_max, effective_max + 2]`, fall through to verdict-driven routing instead of returning `construction_deadlock`. 7 new regression tests in `TestRouteDecisionExtension` (5 positive + 2 negative cases).

### LOW

#### L1. ~~`agent_nodes.py:51` `resolved_config.get("blueprint_name", role)` — toter Code~~ **Fixed Sprint 35**

Wert wird zugewiesen aber nie verwendet. Nur Side-Effect, kein Funktionswert. **Fixed Sprint 35**: Zeile entfernt, Doc-Kommentar erklärt warum `blueprint_name` nicht im Modul gelesen wird (Info-Loss: andere Module/Konsumenten könnten es erwarten).

#### L2. ~~`_max_draft_len = 50000` Magic Number (`agent_nodes.py:434`)~~ **Fixed Sprint 35**

`_max_draft_len = 50000` und `_trunc_warn = "\n\n[… content truncated …]\n\n"` waren function-locals. **Fixed Sprint 35**: Beide als Modul-Konstanten `_MAX_DRAFT_LEN` und `_DRAFT_TRUNCATION_MARKER` extrahiert.

Sollte in `backend/core/config.py` zentralisiert sein.

#### L3. `extension_request` Polling blockiert Workflow-Thread (`moderator_nodes.py:199-213`)

5-Minuten-Block in `await asyncio.sleep(2)` Loop. Während dieser Zeit kann der User **keine** anderen Workflows auf demselben Worker pausieren/fortsetzen, weil das Event im geteilten `workflow_runner._pause_events` Map hängt.

#### L4. ~~Frontend `nodeTypeMap` im `loadFromLayout` ist Identity-Mapping mit Duplikaten (`store.svelte.js:189-220`)~~ **Fixed Sprint 47**

Die Map mappt `wf-initialize → wf-initialize` (Zeile 196-197). Sinnlos. Ein einfaches `n.type` würde reichen.

**Fixed Sprint 47**: Removed the 28-entry identity `nodeTypeMap` from `loadFromLayout`. Every key was identical to its value, so `nodeTypeMap[n.type] || n.type` reduced to plain `n.type`. Replaced with `type: n.type` directly. 30 new tests: 28 parametrised (one per supported node type) verifying the type flows through unchanged, plus fallback identity for unknown types and missing-type defensiveness. All 162 frontend unit tests pass; production build succeeds.

#### L5. ~~`registerAll.js` 643 Zeilen — sollte aufgeteilt werden~~ **Fixed Sprint 48**

Alle Node-Types in einer Datei. Schwer wartbar.

**Fixed Sprint 48**: Split into 3 focused modules + thin orchestrator. `registerAssetNodes.js` (68 lines, 3 assets), `registerWorkflowNodes.js` (210 lines, 25 `wf-*` nodes — 18 agent roles in a `ROLE_TYPES` array loop), `registerEdges.js` (55 lines, 3 semantic + 8 control_flow edges), and `registerAll.js` reduced to 28 lines (orchestrator + re-exports). Public API `registerAllNodeTypes` unchanged. Total 568 → 361 lines; largest file 210 lines. 11 new tests in `registerAll.test.js` covering sub-module isolation, orchestrator totals (28 nodes + 11 edges), idempotence, lookup coverage, and a static guard that `registerAll.js` stays under 60 lines. All 173 frontend unit tests pass; production build succeeds.

#### L6. `interjection_service` (Modul-Singleton) hat keine Persistenz

Bei Server-Restart gehen alle offenen Interjections verloren. User-Eingaben verschwinden.

**Fixed Sprint 49**: `InterjectionService` mirrors its in-memory queue to a SQLite table (`interjections`) in the same `data/blueprints.db` the audit logger and state snapshot already use. New optional `db_path` constructor argument (default `None` keeps in-process tests in pure-memory mode); the module-level singleton is configured with the production default path so the user-facing service is durable. Lazy connection reuse via `threading.RLock` + WAL journal mode (mirrors the M10 audit-logger pattern). Lazy per-session hydration on first access via `_loaded_sessions` set so the per-op cost is one INSERT/UPDATE, not a SELECT. Write-through is best-effort — a transient DB error is logged but does not break the in-memory queue. 14 new tests in `tests/backend/test_interjection_persistence.py` covering write-through (submit/consume/clear touch the DB), metadata JSON round-trip, `consumed_at` timestamp, **restart resilience** (fresh service + same DB re-hydrates pending rows), consumed rows do not resurface, multi-session independence, schema/parent-dir creation, in-memory mode skip, and the singleton default. All 24 pre-existing `test_interjection_service.py` tests + 23 `test_workflow_nodes.py` tests pass unchanged.

---

## 4. Test-Coverage-Lücken

| Bereich | Tests | Coverage |
|---------|-------|----------|
| `models/transactional.py` (Pydantic) | 42 (test_transactional_drafting.py) | ~95% — aber Pydantic-Validation ist trivial |
| `nodes/builder_nodes.py` (Builder) | 0 | 0% — kompletter LLM-Call-Pfad untested |
| `nodes/pragmatist_nodes.py` | 0 | 0% |
| `nodes/angels_advocate_nodes.py` | 0 | 0% |
| `nodes/moderator_nodes.py` (Decision-Branch) | 0 | 0% |
| `workflow_routers.py::route_decision` | 0 | 0% |
| `workflow_compiler.py::compile` (mit transactional template) | 0 | 0% |
| `_save_provenance_batch` | 0 | 0% — DB-Operationen untested |
| `interjection_service` Concurrency | 0 | 0% |
| `eval`-Sandbox in Gates | 0 | 0% — Sicherheit nicht verifiziert |

---

## 5. Empfohlene Reihenfolge

### Sofort (Sicherheit/Korrektheit)

1. **C1**: `eval()` durch AST-Whitelisting ersetzen — Sicherheitslücke
2. **C2**: `operator.add` vs. Replace-Konflikt klären — funktionaler Bug
3. **C3/C4**: Decision-Router-Tests schreiben — Mapping ist fragil

### Hoch (Funktional)

4. **H1**: Modul-Singletons → Redis-Backed
5. **H2**: `current_draft` Accumulator-Logik fixen
6. **H3**: `draft_version >= 5` als Parameter
7. **H4**: Magic String → Enum
8. **H5**: Hardcoded DB-Pfad in `pragmatist_nodes.py` → `BlueprintRepository`
9. **H6**: `is_paused=True` als echte Pause implementieren
10. **H7**: `route_feedback` und Moderator-Extension synchronisieren

### Mittel (Cleanup)

11. Transactional Drafting Template in `modules/workflows/` migrieren ODER Code löschen
12. Integrationstests für `route_decision` und Builder-Loop
13. `eval`-Sandbox-Tests (Sandbox-Escape-Versuche)
14. `registerAll.js` aufteilen
15. `extension_request` Polling non-blocking machen

### Niedrig (Polish)

16. L1-L6 — Dead Code, Magic Numbers, Code-Smells

---

## 6. Offene Fragen

1. **Ist Transactional Drafting gewolltes Feature?** Wenn ja: Template in `modules/workflows/workflow-tpl-transactional-drafting/` migrieren, Tests für Runtime-Pfad schreiben. Wenn nein: Code löschen (1041+ Zeilen + Pydantic + Print-Plugin + Audit-Logik).
2. **Gibt es `uvicorn --workers > 1` in Production?** Falls ja, sind H1, H6, L3 echte Production-Bugs.
3. **Wer hat die Gate-Conditions `eval()`-Struktur designt?** Gibt es einen Anwendungsfall der `__builtins__`-Sandbox rechtfertigt?
4. **Wo kommt `extension_granted` in `route_feedback`** her? Der `route_feedback` nutzt es (`workflow_routers.py:86-99`), aber nur der Moderator setzt es.
