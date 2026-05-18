# Todo-Liste: Bundle-Architektur & Dynamic Agent Roles

> **Stand:** 2026-05-18
> **Quelle:** Session `ses_1cd1d91a0ffeFUyWRTcFRfB3dp` (archiviert 17.05.2026 19:17:38)
> **Plan:** `plans/bundle-architecture-plan.md`

---

## Phase 1: Bundle-Entität (Backend)

### 1.1 Datenmodell

- [ ] **1.1.1** `AgentBundle` Pydantic-Modell in `backend/blueprints/models.py` erstellen
  - Felder: id, name, description, llm_profile_id, role_type_id, role_definition_id, prompt_template_id, tone_profile_id, persona_id, tags, is_active, created_at, updated_at
  - ID-Validierung: `^[a-z0-9][a-z0-9._-]*$`
  - UUID-Generator als default für id
- [ ] **1.1.2** `ResolvedBundle` Pydantic-Modell in `backend/blueprints/models.py` erstellen
  - Felder: bundle_id, bundle_name, llm_profile, role_type, role_definition, prompt_template, tone_profile, system_prompt
- [ ] **1.1.3** Import in `repository.py` hinzufügen

### 1.2 DB-Migration

- [ ] **1.2.1** Migration für `agent_bundles` Tabelle in `backend/blueprints/migrations.py` erstellen
  - CREATE TABLE IF NOT EXISTS
  - Alle Spalten wie im Plan definiert
  - Foreign Keys (optional, SQLite)
- [ ] **1.2.2** Migration testen: `python -c "from backend.blueprints.migrations import run_migrations; ..."`

### 1.3 Repository

- [ ] **1.3.1** `save_bundle()` Methode in `BlueprintRepository` implementieren
  - INSERT OR REPLACE Pattern wie bei anderen Modellen
  - JSON-Serialisierung für tags
- [ ] **1.3.2** `get_bundle()` Methode implementieren
  - SELECT by id
  - `_row_to_bundle()` Konverter
- [ ] **1.3.3** `list_bundles()` Methode implementieren
  - active_only Filter
  - Pagination (limit, offset)
- [ ] **1.3.4** `delete_bundle()` Methode implementieren
- [ ] **1.3.5** `_row_to_bundle()` static method implementieren
  - Graceful fallback für neue Felder (alte DBs)

### 1.4 API-Endpoints

- [ ] **1.4.1** Router-Datei erstellen/erweitern: `backend/api/routers/bundles.py`
- [ ] **1.4.2** `GET /api/v1/bundles` — Liste aller Bundles
  - Query-Params: active_only, limit, offset
  - Response: list[AgentBundle]
- [ ] **1.4.3** `GET /api/v1/bundles/{id}` — Einzelnes Bundle
  - 404 wenn nicht gefunden
- [ ] **1.4.4** `POST /api/v1/bundles` — Neues Bundle erstellen
  - Request: AgentBundle (ohne id, wird generiert)
  - Validierung: alle referenzierten IDs müssen existieren
- [ ] **1.4.5** `PUT /api/v1/bundles/{id}` — Bundle aktualisieren
- [ ] **1.4.6** `DELETE /api/v1/bundles/{id}` — Bundle löschen
- [ ] **1.4.7** Router in `backend/api/app.py` registrieren

### 1.5 Bundle-Resolver

- [ ] **1.5.1** `backend/blueprints/resolver.py` erstellen
- [ ] **1.5.2** `resolve_bundle()` Funktion implementieren
  - Lädt BlueprintLLMProfile, RoleType, RoleDefinition, PromptTemplate, ToneProfile
  - Validiert dass alle Referenzen existieren
  - Wirft ValueError bei fehlenden Referenzen
- [ ] **1.5.3** `_assemble_system_prompt()` Funktion implementieren
  - Reihenfolge: RoleType-Beschreibung → RoleDefinition → PromptTemplate-Inhalt → ToneProfile-Instruktionen
  - Fallback wenn Komponenten fehlen
- [ ] **1.5.4** `GET /api/v1/bundles/{id}/resolve` Endpoint hinzufügen
  - Response: ResolvedBundle

---

## Phase 2: Generic Workflow-Node

### 2.1 Backend: Workflow-Modelle erweitern

- [ ] **2.1.1** `"wf-agent"` zu `WORKFLOW_NODE_TYPES` in `workflow_models.py` hinzufügen
- [ ] **2.1.2** `"wf-agent"` zu `AGENT_NODE_TYPES` hinzufügen
- [ ] **2.1.3** `WorkflowNode.bundle_id: str | None = None` Feld hinzufügen
- [ ] **2.1.4** Validator: `wf-agent` nodes müssen `bundle_id` haben (oder `agent_blueprint_id` als Fallback)
- [ ] **2.1.5** `"wf-agent"` zu `INJECTABLE_AGENT_NODE_TYPES` hinzufügen
- [ ] **2.1.6** Literal-Type in `WorkflowNode.type` um `"wf-agent"` erweitern

### 2.2 Backend: WorkflowCompiler für wf-agent

- [ ] **2.2.1** `WorkflowCompiler.compile()` — `"wf-agent"` Case hinzufügen
- [ ] **2.2.2** Bei `wf-agent`: Bundle auflösen via `resolve_bundle()`
- [ ] **2.2.3** Node-Funktion erstellen mit resolved LLM-Profil und System-Prompt
- [ ] **2.2.4** Test: Workflow mit wf-agent Node kompilieren

### 2.3 Backend: node_functions erweitern

- [ ] **2.3.1** `agent_node_factory()` — bundle_id Parameter hinzufügen
- [ ] **2.3.2** Wenn bundle_id: `resolve_bundle()` aufrufen, System-Prompt aus Bundle
- [ ] **2.3.3** Wenn agent_blueprint_id: altes Verhalten (backward compat)
- [ ] **2.3.4** `_resolve_system_prompt()` — hardcoded dict durch Bundle-basierte Assembly ersetzen
  - Priorität: Bundle system_prompt > PromptTemplate > RoleType default > generic fallback
- [ ] **2.3.5** Hardcoded `role_prompts` dict deprecated markieren (noch nicht löschen)

### 2.4 Frontend: Generic Agent Node Komponente

- [ ] **2.4.1** `frontend/src/components/blueprint/nodes/AgentNode.svelte` erstellen
  - Props: node data (bundle_id, label, etc.)
  - Anzeige: Bundle-Name, Role-Type-Icon, LLM-Profil-Name
  - Farbe: aus RoleType.color
  - Handles: input (top), output (bottom)
- [ ] **2.4.2** Bundle-Daten vom API laden wenn Node gerendert wird
  - Nur bundle_id im Node speichern, nicht ganze Daten
  - API-Call: `GET /api/v1/bundles/{id}` (lazy loading)

### 2.5 Frontend: Registry

- [ ] **2.5.1** `registerAll.js` — `"wf-agent"` Node-Typ registrieren
  - Komponente: `AgentNode.svelte`
  - Kategorie: "workflow"
  - Label: "Agent (Bundle)"
- [ ] **2.5.2** Alte Workflow-Nodes (`wf-strategist` etc.) als deprecated markieren
  - Console.warn beim Registrieren
  - "Soon" Badge in Palette? Oder "Deprecated" Badge

### 2.6 Frontend: DnD und Store

- [ ] **2.6.1** `dnd.js` — `DEFAULT_NODE_DATA` um `"wf-agent"` erweitern
  - Default: `{ type: "wf-agent", data: { bundle_id: null, label: "Agent" } }`
- [ ] **2.6.2** Drop-Handler: Bei `wf-agent` → Bundle-Dropdown im Inspektor
- [ ] **2.6.3** `store.svelte.js` — `"wf-agent"` in `loadFromLayout` Node-Type-Map
  - Mapping: `"wf-agent"` → SvelteFlow node type

### 2.7 Frontend: Inspektor

- [ ] **2.7.1** Inspektor für `wf-agent` Nodes: Bundle-Dropdown anzeigen
  - API-Call: `GET /api/v1/bundles`
  - Dropdown mit allen verfügbaren Bundles
- [ ] **2.7.2** Bei Bundle-Auswahl: Role-Type, LLM, etc. automatisch anzeigen
- [ ] **2.7.3** "Bundle erstellen" Button → öffnet Bundle-Erstellungs-Modal
  - Modal mit Formularen für alle Bundle-Komponenten
  - LLM-Profil Dropdown, Role-Type Dropdown, etc.

### 2.8 Frontend: Palette

- [ ] **2.8.1** `Palette.svelte` — Bundle-Liste vom API laden
  - `loadBundles()` Funktion (wie loadAgentBlueprints)
  - Reactive: $bundles
- [ ] **2.8.2** Neue Kategorie "Bundles" in der Palette
  - Jedes Bundle als draggable Item
  - Drag erstellt `wf-agent` Node mit bundle_id
- [ ] **2.8.3** Bundle-Entity-List (wie PaletteEntityList für andere Entitäten)

---

## Phase 3: Hardcoded Roles auflösen

### 3.1 AgentRole Enum ersetzen

- [ ] **3.1.1** `backend/models/schemas.py` — `AgentRole` Enum deprecated markieren
  - DeprecationWarning beim Import
  - Dokumentation: "Use RoleType.id instead"
- [ ] **3.1.2** `AgentConfig.role` Typ ändern: `AgentRole` → `str`
  - Validierung: muss gültiger RoleType.id sein (optional, zur Laufzeit)
- [ ] **3.1.3** `AgentOutput.role` Typ ändern: `AgentRole` → `str`
- [ ] **3.1.4** `DebateRequest.agent_profile` default: leere Liste `[]` statt 4 feste Rollen
  - Migration Guide: Alte Clients müssen agent_profile explizit setzen

### 3.2 Debate-Router

- [ ] **3.2.1** `backend/api/routers/debate.py` — `continue_debate()` umschreiben
  - Hardcoded 4 AgentConfigs entfernen
  - Agent-Profile aus bestehender Debatte übernehmen (state.agent_profile)
- [ ] **3.2.2** `fork_from_consensus()` umschreiben
  - Gleiches Pattern: aus state übernehmen, nicht hardcoded
- [ ] **3.2.3** `POST /api/v1/debate/bundle` Endpoint erstellen
  - Request: `{ bundle_ids: [...], case: {...} }`
  - Erstellt AgentConfigs aus Bundles
  - Startet Debatte
- [ ] **3.2.4** `POST /api/v1/debate/workflow/{workflow_id}` Endpoint erstellen
  - Lädt Workflow-Definition
  - Extrahiert Bundles aus wf-agent Nodes
  - Startet Debatte mit WorkflowCompiler

### 3.3 Debate-Workflow-Service

- [ ] **3.3.1** `backend/services/debate_workflow.py` — `extract_request_fields()`
  - Hardcoded default agent_profile entfernen
  - Wenn agent_profile leer: aus Bundles/Workflow ableiten
- [ ] **3.3.2** `build_agent_profile_from_bundles(bundle_ids)` Funktion erstellen
  - Lädt jedes Bundle via Repository
  - Erstellt AgentConfig dict: `{ role: role_type_id, llm_profile: llm_profile_id, ... }`
- [ ] **3.3.3** `run_debate_workflow()` — Agent-Profile aus Bundles beziehen
  - Wenn bundle_ids vorhanden: `build_agent_profile_from_bundles()` verwenden
  - Sonst: Fallback auf leere Liste (Fehler wenn kein agent_profile)

### 3.4 Debate-Graph nodes.py

- [ ] **3.4.1** `backend/workflow/nodes.py` — `_AGENT_ORDER` entfernen
  - Oder: dynamisch aus state.agent_profile ableiten
- [ ] **3.4.2** `run_agent_node()` — Agent-Reihenfolge aus State lesen
  - `state["agent_profile"]` enthält Liste von `{role, llm_profile, temperature}`
  - Iteriere über diese Liste statt über `_AGENT_ORDER`

### 3.5 Prompt-Assembly

- [ ] **3.5.1** `backend/workflow/node_functions.py` — `_resolve_system_prompt()` umschreiben
  - Hardcoded `role_prompts` dict entfernen
  - Neue Logik:
    1. Wenn bundle_id: resolved system_prompt verwenden
    2. Wenn prompt_template_id: PromptTemplate-Inhalt verwenden
    3. Wenn role_type_id: RoleType-basierten Default-Prompt verwenden
    4. Fallback: generischer Prompt
- [ ] **3.5.2** RoleType-basierte Default-Prompts konfigurierbar machen
  - Optional: in RoleType Modell ein `default_prompt` Feld
  - Oder: in Argumentation-Patterns speichern

### 3.6 Frontend: Debate-Start

- [ ] **3.6.1** `BlueprintCanvasView.svelte` — "Run Debate" Button umschreiben
  - Bundles aus Canvas-Layout sammeln (wf-agent Nodes)
  - API-Call: `POST /api/v1/debate/bundle` mit Bundle-IDs
- [ ] **3.6.2** Fallback: Wenn keine Bundles im Layout → Hinweis anzeigen
  - "Erstelle zuerst ein Bundle oder platziere Agent-Nodes"

---

## Phase 4: Legacy → Compiled Workflow Migration

### 4.1 WorkflowCompiler als Default-Pfad

- [ ] **4.1.1** `backend/services/debate_workflow.py` — `run_debate_workflow()` erweitern
  - Prüfen: Ist Workflow-Definition vorhanden?
  - Ja: `WorkflowCompiler` verwenden
  - Nein: Fallback auf `debate_graph.py` (legacy)
- [ ] **4.1.2** Feature-Flag oder Config-Option für Migration
  - `USE_WORKFLOW_COMPILER = True/False` in Config
  - Default: True (neuer Pfad)

### 4.2 Canvas-Layout → Workflow-Definition Konverter

- [ ] **4.2.1** `backend/blueprints/converter.py` erstellen (oder bestehende erweitern)
- [ ] **4.2.2** `layout_to_workflow(layout: CanvasLayout) -> WorkflowDefinition` implementieren
  - Iteriere über Layout-Nodes
  - `wf-agent` Nodes → WorkflowNode(type="wf-agent", bundle_id=...)
  - `wf-input`, `wf-gate`, `wf-user-injection` → entsprechende WorkflowNodes
  - Asset-Nodes (llm-profile, role-type, etc.) → ignorieren
- [ ] **4.2.3** Edges konvertieren
  - Canvas-Edges → WorkflowEdges
  - Typ-Mapping: "sequential" → "sequential", "feedback" → "feedback", etc.
- [ ] **4.2.4** Entry-Point setzen (erste wf-input Node oder erste wf-agent Node)
- [ ] **4.2.5** Termination-Conditions aus Layout-Metadata oder Defaults

### 4.3 API: Canvas → Workflow → Debate

- [ ] **4.3.1** `POST /api/v1/debate/from-canvas/{layout_id}` Endpoint
  - Lädt CanvasLayout
  - Konvertiert zu WorkflowDefinition
  - Kompiliert mit WorkflowCompiler
  - Startet Debatte
- [ ] **4.3.2** Response: Debate-Session-ID

### 4.4 Legacy-Code deprecated markieren

- [ ] **4.4.1** `backend/workflow/debate_graph.py` — Deprecation-Warnings
  - `warnings.warn("debate_graph.py is deprecated, use WorkflowCompiler", DeprecationWarning)`
- [ ] **4.4.2** `backend/workflow/nodes.py` — `_AGENT_ORDER` deprecated
- [ ] **4.4.3** Dokumentation aktualisieren

### 4.5 Tests

- [ ] **4.5.1** Integrationstest: Canvas-Layout → Workflow-Definition → Debate
- [ ] **4.5.2** Test: Bundle-Auflösung im WorkflowCompiler
- [ ] **4.5.3** Test: Prompt-Assembly aus Bundles
- [ ] **4.5.4** Test: Legacy-Fallback wenn keine Bundles
- [ ] **4.5.5** Test: Fehlerbehandlung bei ungültigen Bundle-Referenzen

---

## Phase 5: Canvas → Workflow Konvertierung vervollständigen

### 5.1 Frontend: Layout-Konvertierung

- [ ] **5.1.1** `BlueprintCanvasView.svelte` — "Save as Workflow" Button
  - Validiert Canvas-Layout (mindestens 1 wf-agent Node)
  - API-Call: `POST /api/v1/layouts/{id}/convert-to-workflow`
- [ ] **5.1.2** Bundle-Nodes werden als `wf-agent` mit bundle_id gespeichert
- [ ] **5.1.3** Asset-Nodes als Metadata speichern (optional)

### 5.2 Backend: Layout-Konvertierung API

- [ ] **5.2.1** `POST /api/v1/layouts/{id}/convert-to-workflow` Endpoint
  - Lädt CanvasLayout
  - Validiert Bundle-Referenzen
  - Erstellt WorkflowDefinition
  - Speichert in DB
- [ ] **5.2.2** Response: WorkflowDefinition

### 5.3 Bundle-Edge → Control-Flow-Edge Mapping

- [ ] **5.3.1** Edge-Typ-Mapping implementieren
  - Semantic Edges zwischen Bundles → Control-Flow-Edges
  - `uses_llm` Edges → ignorieren (bereits im Bundle)
  - Sequenzielle Anordnung → sequential Edges
- [ ] **5.3.2** Feedback-Loops erkennen (z.B. Moderator → Strategist)

### 5.4 Template-Integration

- [ ] **5.4.1** `WorkflowTemplate` mit `{{bundle_id}}` Placeholdern
  - TemplatePlaceholder type: "bundle_ref"
- [ ] **5.4.2** Template-Instantiation: Bundle-Placeholders mit konkreten IDs füllen
  - `instantiate()` Methode erweitern

---

## Phase 6: Bundle Export/Import

### 6.1 Bundle-Export

- [ ] **6.1.1** `backend/blueprints/exporter.py` erstellen
- [ ] **6.1.2** `export_bundle(bundle_id)` Funktion
  - Bundle + alle referenzierten Entitäten als JSON
  - Metadata: export_version, exported_at
- [ ] **6.1.3** `export_bundle_with_dependencies(bundle_id)` Funktion
  - Inkl. LLM-Profil, RoleType, RoleDefinition, PromptTemplate, ToneProfile
  - Rekursive Dependency-Auflösung

### 6.2 Bundle-Import

- [ ] **6.2.1** `backend/blueprints/importer.py` erweitern
- [ ] **6.2.2** `import_bundle(data: dict)` Funktion
  - Validiert JSON-Struktur
  - Generiert neue IDs bei Kollisionen
  - Erstellt Bundle + referenzierte Entitäten
- [ ] **6.2.3** Konflikt-Handling
  - ID bereits vorhanden: neue ID generieren, Referenzen aktualisieren
  - Option: überschreiben, skip, oder neue ID

### 6.3 Module-System Integration

- [ ] **6.3.1** `ModuleType.BUNDLE` aktivieren
  - Existiert bereits in `backend/modules/models.py`
- [ ] **6.3.2** Bundle als installierbares Modul
  - Manifest: bundle.json mit Dependencies
- [ ] **6.3.3** `manage.sh install-bundle` CLI-Befehl

### 6.4 Frontend: Export/Import UI

- [ ] **6.4.1** Bundle-Export Button im Inspektor
  - Download JSON-Datei
- [ ] **6.4.2** Bundle-Import Dialog
  - File-Upload oder Paste JSON
- [ ] **6.4.3** Drag & Drop von Bundle-Dateien auf Canvas
  - Importiert Bundle, erstellt wf-agent Node

---

## Fortschritt

| Phase | Tasks | Erledigt | Status |
|-------|-------|----------|--------|
| 1. Bundle-Entität | 20 | 0 | ⬜ Nicht begonnen |
| 2. Generic Workflow-Node | 25 | 0 | ⬜ Nicht begonnen |
| 3. Hardcoded Roles | 20 | 0 | ⬜ Nicht begonnen |
| 4. Legacy Migration | 15 | 0 | ⬜ Nicht begonnen |
| 5. Canvas Konvertierung | 15 | 0 | ⬜ Nicht begonnen |
| 6. Bundle Export/Import | 10 | 0 | ⬜ Nicht begonnen |
| **Gesamt** | **105** | **0** | **0%** |

---

## Wichtige Hinweise für Wiederaufnahme

1. **Reihenfolge einhalten:** Phase 1 muss vor Phase 2 abgeschlossen sein (Bundle-Modell existiert)
2. **Backward Compatibility:** Alte Endpoints und Modelle nicht löschen, nur deprecated markieren
3. **DB-Backup:** Vor Migration `data/blueprints.db` backuppen
4. **Tests nach jeder Phase:** Mindestens Smoke-Tests für die geänderten Komponenten
5. **Frontend-Build:** Nach Registry-Änderungen `npm run build` im frontend-Verzeichnis
6. **Backend-Neustart:** Nach Modell-Änderungen Backend neu starten

### Nächster Task: **1.1.1** — `AgentBundle` Pydantic-Modell erstellen
