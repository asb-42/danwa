# Plan: Bundle-Architektur & Dynamic Agent Roles

## Context

**Datum:** 2026-05-18
**Ausgangspunkt:** Session `ses_1cd1d91a0ffeFUyWRTcFRfB3dp` (archiviert 17.05.2026 19:17:38)

### Problemstellung

Die aktuelle Debatte hat 4 hartcodierte Rollen (Strategist, Critic, Optimizer, Moderator) und verwendet 1 LLM für alle Agenten. Das Canvas-System ermöglicht zwar visuelles Komponieren von LLM-Profilen, Role Types, Prompt Templates etc., aber:

1. Es gibt kein Konzept, diese Kombination als wiederverwendbare Einheit ("Bundle") zu speichern
2. Workflow-Nodes (`wf-strategist`, `wf-critic` etc.) sind hartcodiert — keine dynamischen Rollen
3. Der Default-Debate-Pfad (`POST /api/v1/debate`) nutzt die alte `debate_graph.py`, nicht den neuen `WorkflowCompiler`
4. `AgentRole` Enum, `_AGENT_ORDER`, Default-Agent-Profile — alles hardcoded

### Ziel

- **Bundle-Entität**: LLM-Profil + Role-Type + Persona + Prompt + Tone Profile = eine Einheit
- **Generic Workflow-Node**: `wf-agent` statt `wf-strategist`/`wf-critic`/etc. — dynamisch basierend auf Bundle
- **Hardcoded Roles auflösen**: Beliebige Rollen definierbar, jedes Bundle sein eigenes LLM
- **Canvas → Workflow vollständig**: Layout mit Bundles wird zu ausführbarem Workflow

### Bestehende Infrastruktur (wird genutzt, nicht ersetzt)

| Modell | Datei | Status |
|--------|-------|--------|
| `AgentBlueprint` | `backend/blueprints/models.py:350` | Existiert: LLM + Role + Prompt |
| `RoleType` | `backend/blueprints/models.py:306` | Existiert: dynamische Role-Kategorien |
| `RoleDefinition` | `backend/blueprints/models.py:213` | Existiert: role_type_id + prompt_template_id |
| `ToneProfile` | `backend/blueprints/models.py:440` | Existiert |
| `WorkflowCompiler` | `backend/workflow/workflow_compiler.py` | Existiert, aber nicht Default-Pfad |
| `agent_node_factory` | `backend/workflow/node_functions.py` | Existiert, hardcoded role_prompts |
| Canvas Frontend | `frontend/src/components/blueprint/` | Existiert, 2 Modi (blueprint/workflow) |

### Hardcoded Stellen (müssen ersetzt werden)

| Stelle | Datei | Zeilen | Risiko |
|--------|-------|--------|--------|
| `AgentRole` Enum | `backend/models/schemas.py:23-27` | 4 feste Rollen | HIGH |
| `AgentConfig.role` | `backend/models/schemas.py:44` | Typ = AgentRole | HIGH |
| `DebateRequest` default | `backend/models/schemas.py:75-80` | 4 AgentConfigs | HIGH |
| `_AGENT_ORDER` | `backend/workflow/nodes.py:965` | Feste Reihenfolge | HIGH |
| Default agent_profile | `backend/services/debate_workflow.py:163-171` | 4 Rollen | HIGH |
| `continue_debate` hardcoded | `backend/api/routers/debate.py:488-493` | 4 AgentConfigs | HIGH |
| `fork_from_consensus` hardcoded | `backend/api/routers/debate.py:618-623` | 4 AgentConfigs | HIGH |
| `role_prompts` dict | `backend/workflow/node_functions.py:847-855` | 7 feste Prompts | MEDIUM |
| `WORKFLOW_NODE_TYPES` | `backend/blueprints/workflow_models.py:26-39` | 12 feste Typen | MEDIUM |
| `AGENT_NODE_TYPES` | `backend/blueprints/workflow_models.py:42-50` | 7 feste Typen | MEDIUM |
| `DEFAULT_NODE_DATA` | `frontend/src/lib/blueprint/dnd.js:12-80` | Feste Defaults | MEDIUM |
| Node type map | `frontend/src/lib/blueprint/store.svelte.js:175-194` | Feste Map | MEDIUM |
| Node Registry | `frontend/src/lib/blueprint/registerAll.js` | 17 feste Node-Typen | MEDIUM |

---

## Phasen-Übersicht

```
Phase 1: Bundle-Entität (Backend)          [~20 Tasks]
Phase 2: Generic Workflow-Node              [~25 Tasks]
Phase 3: Hardcoded Roles auflösen           [~20 Tasks]
Phase 4: Legacy → Compiled Workflow         [~15 Tasks]
Phase 5: Canvas → Workflow Konvertierung    [~15 Tasks]
Phase 6: Bundle Export/Import               [~10 Tasks]
```

---

## Phase 1: Bundle-Entität (Backend)

**Ziel:** `AgentBundle` Modell, das LLM-Profil + Role-Type + Persona + Prompt + Tone Profile als eine Einheit verknüpft.

### 1.1 Datenmodell

**Datei:** `backend/blueprints/models.py`

Neues Modell `AgentBundle`:

```python
class AgentBundle(BaseModel):
    """A reusable composition of LLM + Role-Type + Persona + Prompt + Tone Profile.

    Represents a complete debate agent configuration that can be placed
    as a node on the Canvas and referenced in Workflows.
    """
    id: str
    name: str
    description: str = ""
    # Core composition
    llm_profile_id: str        # References BlueprintLLMProfile.id
    role_type_id: str          # References RoleType.id (NOT RoleDefinition — more flexible)
    role_definition_id: str | None   # Optional: specific RoleDefinition override
    prompt_template_id: str | None   # Optional: specific PromptTemplate override
    tone_profile_id: str | None      # Optional: ToneProfile for communication style
    persona_id: str | None           # Optional: legacy AgentPersona reference
    # Metadata
    tags: list[str] = []
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
```

**Unterschied zu `AgentBlueprint`:**
- `AgentBlueprint` verknüpft LLM + RoleDefinition + PromptTemplate
- `AgentBundle` verknüpft LLM + RoleType (+ optional RoleDefinition) + PromptTemplate + ToneProfile
- Bundle ist die "höhere" Kompositionseinheit für Workflow-Nodes

### 1.2 DB-Migration

**Datei:** `backend/blueprints/migrations.py`

Neue Tabelle `agent_bundles`:
- id (TEXT PK)
- name (TEXT NOT NULL)
- description (TEXT)
- llm_profile_id (TEXT NOT NULL, FK → blueprint_llm_profiles)
- role_type_id (TEXT NOT NULL, FK → role_types)
- role_definition_id (TEXT, FK → role_definitions)
- prompt_template_id (TEXT, FK → prompt_templates)
- tone_profile_id (TEXT, FK → tone_profiles)
- persona_id (TEXT)
- tags_json (TEXT)
- is_active (INTEGER)
- created_at (TEXT)
- updated_at (TEXT)

### 1.3 Repository

**Datei:** `backend/blueprints/repository.py`

Neue Methoden:
- `save_bundle(bundle: AgentBundle) -> None`
- `get_bundle(bundle_id: str) -> AgentBundle | None`
- `list_bundles(active_only=True, limit=50, offset=0) -> list[AgentBundle]`
- `delete_bundle(bundle_id: str) -> bool`
- `_row_to_bundle(row) -> AgentBundle`

### 1.4 API-Endpoints

**Datei:** `backend/api/routers/blueprints.py` (oder neue Datei)

- `GET /api/v1/bundles` — Liste aller Bundles
- `GET /api/v1/bundles/{id}` — Einzelnes Bundle
- `POST /api/v1/bundles` — Neues Bundle erstellen
- `PUT /api/v1/bundles/{id}` — Bundle aktualisieren
- `DELETE /api/v1/bundles/{id}` — Bundle löschen
- `GET /api/v1/bundles/{id}/resolve` — Bundle auflösen (alle referenzierten Entitäten inline)

### 1.5 Bundle-Resolver

**Datei:** `backend/blueprints/resolver.py` (neu)

Funktion `resolve_bundle(bundle: AgentBundle) -> ResolvedBundle`:
- Löst alle Referenzen auf (LLM-Profil, RoleType, RoleDefinition, PromptTemplate, ToneProfile)
- Validiert dass alle Referenzen existieren
- Erstellt ein `ResolvedBundle` mit allen inline-Daten für die Workflow-Execution

```python
class ResolvedBundle(BaseModel):
    bundle_id: str
    bundle_name: str
    llm_profile: BlueprintLLMProfile
    role_type: RoleType
    role_definition: RoleDefinition | None
    prompt_template: PromptTemplate | None
    tone_profile: ToneProfile | None
    system_prompt: str  # Assembled from role_type + role_definition + prompt_template + tone_profile
```

---

## Phase 2: Generic Workflow-Node

**Ziel:** Statt `wf-strategist`, `wf-critic` etc. einen generischen `wf-agent` Node, der ein Bundle referenziert.

### 2.1 Backend: Workflow-Modelle erweitern

**Datei:** `backend/blueprints/workflow_models.py`

- `"wf-agent"` zu `WORKFLOW_NODE_TYPES` hinzufügen
- `"wf-agent"` zu `AGENT_NODE_TYPES` hinzufügen
- `WorkflowNode` erweitern: `bundle_id: str | None = None` (alternativ zu `agent_blueprint_id`)
- Validator: `wf-agent` nodes müssen `bundle_id` haben
- `INJECTABLE_AGENT_NODE_TYPES` um `"wf-agent"` erweitern

### 2.2 Backend: WorkflowCompiler für wf-agent

**Datei:** `backend/workflow/workflow_compiler.py`

- Neuen Node-Typ `"wf-agent"` im Compiler behandeln
- Bei `wf-agent`: Bundle auflösen → LLM-Profil + System-Prompt + Role-Type
- Node-Funktion dynamisch erstellen basierend auf Bundle-Konfiguration

### 2.3 Backend: node_functions erweitern

**Datei:** `backend/workflow/node_functions.py`

- `agent_node_factory()` um Bundle-Support erweitern
- Wenn `bundle_id` vorhanden: `resolve_bundle()` aufrufen, System-Prompt aus Bundle zusammensetzen
- Hardcoded `role_prompts` dict durch Bundle-basierte Prompt-Assembly ersetzen
- Fallback: Falls kein Bundle, altes Verhalten beibehalten (backward compat)

### 2.4 Frontend: Generic Agent Node Komponente

**Datei:** `frontend/src/components/blueprint/nodes/AgentNode.svelte` (neu)

- Generische Node-Komponente für `wf-agent`
- Zeigt Bundle-Name, Role-Type-Icon, LLM-Profil-Name
- Farbe basierend auf RoleType.color
- Keine festen Node-Typen mehr für jede Rolle

### 2.5 Frontend: Registry

**Datei:** `frontend/src/lib/blueprint/registerAll.js`

- `"wf-agent"` Node-Typ registrieren mit `AgentNode.svelte`
- Alte hartcodierte Workflow-Nodes (`wf-strategist` etc.) als deprecated markieren
- Palette: "Agent (Bundle)" als neuer Eintrag in Workflow-Node-Sektion

### 2.6 Frontend: DnD und Store

**Datei:** `frontend/src/lib/blueprint/dnd.js`

- `DEFAULT_NODE_DATA` um `"wf-agent"` erweitern
- Drop-Handler: Bei `wf-agent` → Bundle-Dropdown im Inspektor

**Datei:** `frontend/src/lib/blueprint/store.svelte.js`

- `loadFromLayout`: `"wf-agent"` in der Node-Type-Map unterstützen

### 2.7 Frontend: Inspektor

**Datei:** `frontend/src/components/blueprint/Inspector.svelte` (oder relevante Datei)

- Für `wf-agent` Nodes: Bundle-Dropdown anzeigen
- Bundle-Auswahl lädt automatisch Role-Type, LLM, etc.
- "Bundle erstellen" Button → öffnet Bundle-Erstellungs-Modal

### 2.8 Frontend: Palette

**Datei:** `frontend/src/components/blueprint/Palette.svelte`

- Bundle-Liste vom API laden (ähnlich wie agentBlueprints)
- Bundles als eigene Kategorie in der Palette
- Jedes Bundle ist draggable → erstellt `wf-agent` Node

---

## Phase 3: Hardcoded Roles auflösen

**Ziel:** `AgentRole` Enum und alle hardcoded Stellen durch dynamische Role-Type-Referenzen ersetzen.

### 3.1 AgentRole Enum ersetzen

**Datei:** `backend/models/schemas.py`

- `AgentRole` Enum deprecated markieren
- Neuer Typ: `AgentRoleRef = str` (referenziert RoleType.id)
- `AgentConfig.role` Typ ändern: `AgentRole` → `str` (RoleType.id)
- `AgentOutput.role` Typ ändern: `AgentRole` → `str`
- `DebateRequest.agent_profile` default: leere Liste statt 4 feste Rollen

### 3.2 Debate-Router

**Datei:** `backend/api/routers/debate.py`

- `continue_debate()`: Hardcoded 4 AgentConfigs durch dynamische aus Bundle/Workflow ersetzen
- `fork_from_consensus()`: Gleiches Pattern
- Neue Endpoints für Bundle-basierte Debatten:
  - `POST /api/v1/debate/bundle` — Debatte mit bestimmten Bundles starten
  - `POST /api/v1/debate/workflow/{workflow_id}` — Debatte aus Workflow-Definition starten

### 3.3 Debate-Workflow-Service

**Datei:** `backend/services/debate_workflow.py`

- `extract_request_fields()`: Hardcoded default agent_profile entfernen
- `run_debate_workflow()`: Agent-Profile aus Bundles/Workflow-Definition beziehen
- Neue Funktion: `build_agent_profile_from_bundles(bundle_ids: list[str]) -> list[dict]`

### 3.4 Debate-Graph nodes.py

**Datei:** `backend/workflow/nodes.py`

- `_AGENT_ORDER` entfernen oder durch dynamische Liste ersetzen
- `run_agent_node()`: Agent-Reihenfolge aus State/Workflow-Definition lesen

### 3.5 Prompt-Assembly

**Datei:** `backend/workflow/node_functions.py`

- `_resolve_system_prompt()`: Hardcoded `role_prompts` dict entfernen
- Stattdessen: Prompt aus RoleType + RoleDefinition + PromptTemplate + ToneProfile zusammensetzen
- RoleType-basierte Default-Prompts (optional, konfigurierbar)

### 3.6 Frontend: Debate-Start

**Datei:** `frontend/src/views/BlueprintCanvasView.svelte`

- "Run Debate" Button: Bundles aus Canvas-Layout sammeln
- API-Call mit Bundle-IDs statt hardcoded Rollen
- Fallback: Wenn keine Bundles, altes Verhalten (backward compat)

---

## Phase 4: Legacy → Compiled Workflow Migration

**Ziel:** Die default Debate-API auf den `WorkflowCompiler` umstellen.

### 4.1 WorkflowCompiler als Default-Pfad

**Datei:** `backend/services/debate_workflow.py`

- `run_debate_workflow()`: Zuerst prüfen ob Workflow-Definition vorhanden
- Wenn ja: `WorkflowCompiler` verwenden
- Wenn nein: Fallback auf legacy `debate_graph.py`

### 4.2 Canvas-Layout → Workflow-Definition Konverter

**Datei:** `backend/blueprints/converter.py` (neu oder erweitern)

- `layout_to_workflow(layout: CanvasLayout) -> WorkflowDefinition`
- Erkennt `wf-agent` Nodes → erstellt WorkflowNode mit bundle_id
- Erkennt Asset-Nodes → ignoriert (nur Workflow-Nodes relevant)
- Erkennt Edges → erstellt WorkflowEdge mit korrektem Typ
- Setzt entry_point, termination_conditions

### 4.3 API: Canvas → Workflow → Debate

**Datei:** `backend/api/routers/debate.py`

- `POST /api/v1/debate/from-canvas/{layout_id}`:
  1. Canvas-Layout laden
  2. Zu Workflow-Definition konvertieren
  3. WorkflowCompiler ausführen
  4. Debatte starten

### 4.4 Legacy-Code deprecated markieren

**Datei:** `backend/workflow/debate_graph.py`

- Deprecation-Warnings hinzufügen
- Dokumentation: "Use WorkflowCompiler instead"

### 4.5 Tests

- Integrationstests für Canvas → Workflow → Debate Pfad
- Tests für Bundle-Auflösung im WorkflowCompiler
- Tests für Prompt-Assembly aus Bundles

---

## Phase 5: Canvas → Workflow Konvertierung vervollständigen

**Ziel:** `convertLayoutToWorkflow()` erkennt Bundles und übersetzt sie korrekt.

### 5.1 Frontend: Layout-Konvertierung

**Datei:** `frontend/src/views/BlueprintCanvasView.svelte`

- "Save as Workflow" Button: Canvas-Layout mit Bundles zu Workflow speichern
- Bundle-Nodes werden als `wf-agent` mit bundle_id gespeichert
- Asset-Nodes (LLM, RoleType, etc.) werden als Metadata gespeichert

### 5.2 Backend: Layout-Konvertierung API

**Datei:** `backend/api/routers/blueprints.py`

- `POST /api/v1/layouts/{id}/convert-to-workflow`
- Validiert dass alle Bundle-Referenzen existieren
- Erstellt WorkflowDefinition mit wf-agent Nodes

### 5.3 Bundle-Edge → Control-Flow-Edge Mapping

- Semantic Edges zwischen Bundles werden zu Control-Flow-Edges
- `uses_llm` Edges werden ignoriert (bereits im Bundle enthalten)
- Sequenzielle Anordnung der Bundles wird zur Workflow-Reihenfolge

### 5.4 Template-Integration

**Datei:** `backend/blueprints/workflow_models.py`

- WorkflowTemplates mit `{{bundle_id}}` Placeholdern unterstützen
- Template-Instantiation: Bundle-Placeholders mit konkreten Bundle-IDs füllen

---

## Phase 6: Bundle Export/Import

**Ziel:** Bundles als portable Einheiten exportieren/importieren.

### 6.1 Bundle-Export

**Datei:** `backend/blueprints/exporter.py` (neu)

- `export_bundle(bundle_id: str) -> dict`: Bundle + alle referenzierten Entitäten
- Optional: `export_bundle_with_dependencies()` — inkl. LLM-Profil, RoleType, etc.
- Format: JSON mit Metadata-Version

### 6.2 Bundle-Import

**Datei:** `backend/blueprints/importer.py` (erweitern)

- `import_bundle(data: dict) -> AgentBundle`: Importiert Bundle aus JSON
- Konflikt-Handling: ID-Kollisionen erkennen, neue IDs generieren
- Validierung: Referenzen auf existierende Entitäten prüfen

### 6.3 Module-System Integration

**Datei:** `backend/modules/models.py`

- `ModuleType.BUNDLE` aktivieren (existiert bereits als Enum-Wert)
- Bundle als installierbares Modul mit Manifest
- Dependencies: LLM-Profil, RoleType, etc.

### 6.4 Frontend: Export/Import UI

- Bundle-Export Button im Inspektor
- Bundle-Import Dialog
- Drag & Drop von Bundle-Dateien auf Canvas

---

## Risiken & Abhängigkeiten

| Risiko | Phase | Auswirkung | Gegenmaßnahme |
|--------|-------|------------|---------------|
| Breaking Changes in API | 3 | Alte Clients brechen | Backward-compat Defaults, Deprecation-Warnungen |
| WorkflowCompiler Bugs | 4 | Debatten funktionieren nicht | Umfangreiche Tests, Fallback auf Legacy |
| Frontend-Performance | 2 | Svelte 5 Reactivity-Probleme | Wie bisher: nur IDs laden, nicht ganze Objekte |
| DB-Migration | 1 | Bestehende Daten betroffen | Migration idempotent, Backup vorher |
| Prompt-Qualität | 3 | Schlechtere Debate-Ergebnisse | Prompt-Assembly sorgfältig testen |
