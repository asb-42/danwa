# Rollen-Typen-Abstraktion — Umsetzungsplan

> **Datum:** 2026-05-13  
> **Status:** In Umsetzung — Backend & Frontend Kernimplementierung abgeschlossen (2026-05-13)  
> **Abhängigkeiten:** Keine (kann parallel zu anderen Sprints laufen)

---

## 1. Ausgangslage

Die Danwa-Plattform hat derzeit vier fest verdrahtete Agenten-Rollen:
`strategist`, `critic`, `optimizer`, `moderator`.

Diese sind hart als `Literal`-Typen in folgenden Stellen verankert:

| Datei | Stelle |
|---|---|
| `backend/blueprints/workload_models.py` | `AGENT_NODE_TYPES`, `WORKFLOW_NODE_TYPES`, `WorkflowNode.type` Literal, `INJECTABLE_AGENT_NODE_TYPES` |
| `backend/workflow/workflow_compiler.py` | `AGENT_NODE_TYPES`-Import, `_create_node_function`-Dispatch |
| `backend/workflow/node_functions.py` | `agent_node_factory`, `moderator_node_factory` |
| `backend/blueprints/compiler.py` | `_validate_tone_profile_edges` → `injectable_types`-Set |
| `frontend/src/components/blueprint/forms/WorkflowNodeForm.svelte` | `AGENT_NODE_TYPES`-Array, `NODE_TYPE_LABELS`-Map |
| `frontend/src/lib/workflow/oob.js` | Out-of-Band-Router `INJECTABLE_WORKFLOW_NODE_TYPES` |
| `frontend/src/lib/workflow/mapper.js` | Workflow-Mapper |
| Verschiedene Prompt-Dateien | `profiles/prompts/default/` und `profiles/prompts/variants/` |
| Profil-YAMLs | `profiles/agents/*.yaml` |

**Fact-Checker** existiert bereits als `role_type_id` in `RoleDefinition`, hat aber **noch keinen** Eintrag in `AGENT_NODE_TYPES`/`WORKFLOW_NODE_TYPES` und keine eigene Frontend-Node.

---

## 2. Zielarchitektur: Vierstufiges Rollen-Modell

```
┌─────────────────────────────────────────────────────────────────┐
│  Ebene 1: Funktionale Rolle (Was macht der Agent?)              │
│  → role_type_id auf RoleDefinition / WorkflowNode.type          │
├─────────────────────────────────────────────────────────────────┤
│  Ebene 2: Formatorische Rolle (In welcher Gesprächsform?)       │
│  → mode auf RoleDefinition (interviewer, advocate, adversary…)  │
├─────────────────────────────────────────────────────────────────┤
│  Ebene 3: Argumentationsmuster / Agenten-Persönlichkeit          │
│  → argumentation_pattern auf RoleDefinition                      │
│  (kantian, hegelian, utilitarian, stoic, aristotelian, socratic)│
├─────────────────────────────────────────────────────────────────┤
│  Ebene 4: Tone Profile (Stimmung / Aszendenz)                   │
│  → ToneRef per injects_config-Edge                              │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 Neue Rollen im Detail

#### 2.1.1 Funktionale Rollen (Ebene 1) — neue `role_type_id`-Werte

| `role_type_id`    | Icon | Farbe   | Beschreibung                                              |
|--------------------|------|---------|-----------------------------------------------------------|
| `strategist`       | 🧠   | `#8b5cf6` (Violett) | Bestehend — Strukturierung, Themenextraktion             |
| `critic`           | 🔍   | `#ef4444` (Rot)     | Bestehend — Schwachstellenidentifikation                  |
| `fact-checker`     | ✅   | `#10b981` (Grün)    | Bestehend als ID, noch nicht als Node registriert         |
| `optimizer`        | ⚡   | `#f59e0b` (Amber)   | Bestehend — Synthese, Verfeinerung                        |
| `analyst`          | 📊   | `#06b6d4` (Cyan)    | **Neu** — Tiefgehende Analyse, Datenauswertung           |
| `creative`         | 💡   | `#ec4899` (Pink)    | **Neu** — Perspektivwechsel, Brainstorming               |
| `moderator`        | 🎯   | `#6366f1` (Indigo)  | Bestehend — Konsensbildung, Abschlussbewertung           |
| `interviewer`      | 🎤   | `#f97316` (Orange)  | **Neu** — Gezieltes Nachfragen (formatorisch, kein eigener funktionaler Arbeitsschritt) |
| `advocate`         | 🛡️   | `#8b5cf6` (Violett) | **Neu** — Einseitige Verteidigung (Streitgespräch)      |
| `adversary`        | ⚔️   | `#ef4444` (Rot)     | **Neu** — Aktive Konfrontation (Streitgespräch)          |
| `mediator`         | 🤝   | `#10b981` (Grün)    | **Neu** — Vermittlung, Kompromissfindung                 |
| `referee`          | 🏅   | `#6366f1` (Indigo)  | **Neu** — Regeln-Durchsetzen, Fairness                   |

> **Hinweis zu interviewer / advocate / adversary / mediator / referee:**  
> Diese sind **formatorische** Rollen und keine funktionalen Arbeitsschritte. Sie werden primär über das `mode`-Feld der `RoleDefinition` gesteuert. In `AGENT_NODE_TYPES` werden sie **nicht** als eigene Node-Typen aufgenommen — stattdessen wird der funktionale `role_type_id` beibehalten (z.B. `critic` mit `mode: "interviewer"`). Siehe Abschnitt 3.

#### 2.1.2 Abgrenzung: Was ist Funktion vs. Formatorik?

- **Funktional** = Ein eigenständiger Arbeitsschritt in der Pipeline, der eine **andere** Aufgabe erfüllt und ein **anderes** Ergebnis liefert.
- **Formatorisch** = Die Art und Weise, wie ein funktionaler Arbeitsschritt ausgeführt wird. Ein Interviewer-Critic *kritisiert*, aber in Interview-Form.

**Faustregel:** Hat die Rolle eine eigene Position in der Pipeline (bevorzugt einen eigenen Output, der vom nächsten Agenten konsumiert wird) → **eigener `role_type_id`**. Beeinflusst nur die Art des Vortrags → **`mode`-Feld**.

---

## 3. Umsetzungsmaßnahmen — Backend

### 3.1 Datenmodelle anpassen

**Datei:** `backend/blueprints/workload_models.py`

**a) `RoleType`-Model um `mode`-Feld erweitern:**

Neues Feld:
```python
# In RoleType:
category: Literal["functional", "formative"] = "functional"
```
→ Erlaubt die Unterscheidung zwischen funktionalen Rollen (eigener Node) und formatorischen Rollen (Modus eines funktionalen Agenten).

Optional: Hilfsliste der verfügbaren Modi:
```python
AVAILABLE_MODES: dict[str, list[str]] = {
    "strategist": ["advocate"],
    "critic": ["adversary", "interviewer", "devils_advocate"],
    "analyst": ["interviewer"],
    "moderator": ["mediator", "referee", "facilitator"],
    "creative": [],
    "fact-checker": [],
    "optimizer": [],
}
```

**b) `RoleDefinition`-Model um `argumentation_pattern`-Feld erweitern:**

```python
class RoleDefinition(BaseModel):
    ...
    argumentation_pattern: str | None = None  # kantian, hegelian, utilitarian, stoic, ...
    ...
```

**c) `WorkloadNode` Literal-Typen erweitern:**

```python
WORKFLOW_NODE_TYPES: list[str] = [
    "wf-input",
    "wf-initialize",
    "wf-strategist",
    "wf-critic",
    "wf-fact-checker",       # ← NEU
    "wf-optimizer",
    "wf-moderator",
    "wf-analyst",             # ← NEU
    "wf-creative",            # ← NEU
    "wf-user-injection",
    "wf-gate",
    "wf-tone-profile",
]

AGENT_NODE_TYPES: list[str] = [
    "wf-strategist",
    "wf-critic",
    "wf-fact-checker",        # ← NEU
    "wf-optimizer",
    "wf-moderator",
    "wf-analyst",              # ← NEU
    "wf-creative",             # ← NEU
]

INJECTABLE_AGENT_NODE_TYPES: list[str] = [
    "wf-strategist",
    "wf-critic",
    "wf-fact-checker",        # ← NEU
    "wf-optimizer",
    "wf-moderator",
    "wf-analyst",              # ← NEU
    "wf-creative",             # ← NEU
]
```

### 3.2 Prompt-Migration

**Aktueller Zustand:** Die Prompt-Varianten `kantian`, `hegelian`, `steiner`, `dialectic` liegen unter `profiles/prompts/variants/` und enthalten rollo-spezifische Prompts (z.B. `kantian/strategist.md`). Das ist strukturell falsch, wie im Gespräch festgestellt.

**Migration:**

| Aktuell (falsch) | Zukunft (richtig) |
|---|---|
| `prompts/variants/kantian/strategist.md` | → **Argumentation Pattern** `kantian` in `RoleDefinition` |
| `prompts/variants/kantian/critic.md` | → Argumentation Pattern `kantian` in `RoleDefinition` |
| `prompts/variants/dialectic/strategist.md` | → **Workflow-Template** "Hegelsche Dialektik" |
| `prompts/variants/dialectic/critic.md` | → Workflow-Template "Hegelsche Dialektik" |
| `prompts/variants/steiner/strategist.md` | → **Argumentation Pattern** `steiner` in `RoleDefinition` |
| `prompts/default/strategist.md` | Bleibt als **Default-Prompt** für `strategist`-RoleType |

**Konkrete Schritte:**

1. **Neue Prompts erstellen:** Für jedes Argumentation Pattern × Rolle eine systematische Promptsammlung als `argumentation_pattern/{pattern}/{role_type_id}.md`:
   ```
   profiles/argumentation-patterns/
   ├── kantian/
   │   ├── strategist.md
   │   ├── critic.md
   │   ├── fact-checker.md
   │   └── analyst.md
   ├── hegelian/
   ├── utilitarian/
   ├── stoic/
   ├── aristotelian/
   └── socratic/
   ```

2. **Dialectic-Prompts → Workflow-Template:** Die Dialektik-Variante wird zum Workflow-Template "Hegelsche Dialektik" (These via Strategist → Antithese via Critic → Synthese via Optimizer).

3. **Alte Varianten-Directory:** `prompts/variants/` wird deprecated. Migrationsskript zum Verschieben.

**Prompt-Assembly Pipeline (in `node_functions.py`):**

```python
def assemble_system_prompt(resolved_config, tone_profile=None):
    """
    1. Base:    argumentation_pattern-Prompt (z.B. kantian/strategist.md)
    2. Layer:   role_type-Prompt (default/strategist.md)
    3. Layer:   workflow-variant-Prompt (z.B. "no_tables")
    4. Layer:   Tone-Profile-Injection
    """
    pass
```

### 3.3 Backend-Service-Schicht

**Datei:** `backend/services/prompt_service.py`

- Methode `get_argumentation_pattern(role_type_id, pattern_name, language)` hinzufügen
- Methode `assemble_full_prompt(role_type_id, argumentation_pattern, tone_profile, workflow_variant, language)` erstellen
- Bestehende `get_prompt_content()` beibehalten für Abwärtskompatibilität

### 3.4 Compiler-Service anpassen

**Datei:** `backend/blueprints/compiler.py`

- `ResolvedAgent` um Felder erweitern:
  ```python
  argumentation_pattern: str = ""
  argumentation_pattern_icon: str = "🧠"
  mode: str | None = None  # formatorischer Modus
  ```
- Validierung: Prüfen, dass `argumentation_pattern`-Referenz existiert (neuen Katalog pflegen)
- `_validate_tone_profile_edges.injectable_types` automatisch aus `AGENT_NODE_TYPES` ableiten statt hart zu codieren

### 3.5 Workflow-Compiler anpassen

**Datei:** `backend/workflow/workflow_compiler.py`

- `AGENT_NODE_TYPES`-Import aktualisieren
- `_create_node_function`: Kein `elif`-Chain für neue Node-Typen nötig — `agent_node_factory` kann **alle** Agent-Node-Typen bedienen, da die Unterscheidung über `role` (aus `resolved_config.role`) läuft
- `moderator_node_factory` bleibt Sonderfall

### 3.6 Node Functions anpassen

**Datei:** `backend/workflow/node_functions.py`

- `_resolve_system_prompt()`: Um Prompt-Assembly-Pipeline erweitern (Ebene 1→2→3→4)
- `role_prompts`-Fallback-Dict um neue Rollen ergänzen:
  ```python
  role_prompts = {
      "strategist": "...",
      "critic": "...",
      "fact-checker": "Du bist ein Fakten-Checker. Verifiziere Behauptungen...",
      "analyst": "Du bist ein Analyst. Führe eine tiefgehende Datenanalyse durch...",
      "creative": "Du bist ein kreativer Denker. Entwickle ungewöhnliche Lösungsansätze...",
      "moderator": "...",
  }
  ```

### 3.7 Repository anpassen

**Datei:** `backend/blueprints/repository.py`

- `list_role_definitions()` um optionalen Filter `argumentation_pattern` erweitern
- Neue Hilfsmethode `list_argumentation_patterns() -> list[str]` hinzufügen (liest verfügbare Verzeichnisse)
- Neue Methode `save_argumentation_pattern()` / `get_argumentation_pattern()` für die Persistierung

### 3.8 Datenbank-Migration

**Datei:** `backend/blueprints/migrations.py`

Neue Migrationen:
1. `role_definitions.argumentation_pattern` TEXT-Spalte hinzufügen
2. `role_types.category` TEXT-Spalte hinzufügen (Default: "functional")
3. Neue Tabelle `argumentation_patterns` (id, name, description, prompt_templates_json)

### 3.9 API-Endpunkte

**Datei:** `backend/api/routers/role_definitions.py`

- `GET /role-definitions?argumentation_pattern=`-Filter hinzufügen
- Neuer Router `argumentation_patterns.py`:
  - `GET /argumentation-patterns` — Liste verfügbarer Patterns
  - `GET /argumentation-patterns/{name}` — Einzelnes Pattern mit Prompts

### 3.10 Workflow-Templates aktualisieren

**Datei:** `backend/workflow/workflow_templates.py`

- **"Hegelian Debate"**: `strategist (these) → critic (antithese) → optimizer (synthese) → moderator`
  - Modus: `moderator.mode = "facilitator"`
- **"Devil's Advocate"**: `strategist → critic (mode: adversary) → optimizer → moderator`
- **"Interview"**: `strategist (mode: interviewer) → analyst (mode: interviewer) → moderator`
- **"Mediation"**: `strategist → critic → mediator (mode: mediator) → moderator`

---

## 4. Umsetzungsmaßnahmen — Frontend

### 4.1 Neue Node-Komponenten

Für jede neue funktionale Rolle eine eigene Svelte-Komponente:

| Datei | Basiskomponente | Icon | Farbe |
|---|---|---|---|
| `FactCheckerNode.svelte` | Analog `StrategistNode` | ✅ | `#10b981` |
| `AnalystNode.svelte` | Analog `StrategistNode` | 📊 | `#06b6d4` |
| `CreativeNode.svelte` | Analog `StrategistNode` | 💡 | `#ec4899` |

> **Wichtig:** Für formatorische Rollen (interviewer, advocate, adversary usw.) werden **keine** eigenen Node-Komponenten benötigt, da sie über die `RoleDefinition` und das `mode`-Feld gesteuert werden und denselben funktionalen Node-Typ verwenden.

### 4.2 Node-Registry aktualisieren

**Datei:** `frontend/src/lib/blueprint/registerAll.js`

Neue Node-Typen registrieren:
```javascript
import FactCheckerNode from '../components/blueprint/nodes/FactCheckerNode.svelte';
import AnalystNode from '../components/blueprint/nodes/AnalystNode.svelte';
import CreativeNode from '../components/blueprint/nodes/CreativeNode.svelte';

registerNode({ type: 'wf-fact-checker', component: FactCheckerNode, category: 'workflow', ... });
registerNode({ type: 'wf-analyst', component: AnalystNode, category: 'workflow', ... });
registerNode({ type: 'wf-creative', component: CreativeNode, category: 'workflow', ... });
```

### 4.3 WorkflowNodeForm anpassen

**Datei:** `frontend/src/components/blueprint/forms/WorkflowNodeForm.svelte`

- `AGENT_NODE_TYPES`-Array um neue Typen erweitern
- `NODE_TYPE_LABELS`-Map um neue Einträge erweitern
- Neues Feld `argumentation_pattern` als Dropdown (wenn Agent-Node ausgewählt)
- Neues Feld `mode` als Dropdown (möglich, abhängig von `role_type_id`)

### 4.4 Palette anpassen

**Datei:** `frontend/src/components/blueprint/Palette.svelte`

- Neue Workflow-Nodes erscheinen automatisch durch Registrierung (Abschnitt 4.2)
- Reihenfolge im Workflow-Bereich der Palette festlegen

### 4.5 Store anpassen

**Datei:** `frontend/src/lib/blueprint/store.svelte.js`

- `nodeTypeMap` in `loadFromLayout()` um neue Typen erweitern

### 4.6 Mapping-Schicht aktualisieren

**Datei:** `frontend/src/lib/workflow/mapper.js`

- Neue Node-Typen in den Mapper-Logiken ergänzen

### 4.7 Out-of-Band Router aktualisieren

**Datei:** `frontend/src/lib/workflow/oob.js`

- `INJECTABLE_WORKFLOW_NODE_TYPES` erweitern

---

## 5. Prompt-Refactoring

### 5.1 Neue Verzeichnisstruktur

```
profiles/
├── prompts/
│   ├── default/                    # Wie bisher — Default-Prompts pro Rolle
│   │   ├── strategist.md
│   │   ├── strategist-en.md
│   │   ├── critic.md
│   │   └── ...
│   ├── argumentation-patterns/     # NEU — Prompts pro (Pattern × Rolle)
│   │   ├── kantian/
│   │   │   ├── strategist.md
│   │   │   ├── critic.md
│   │   │   ├── fact-checker.md
│   │   │   └── analyst.md
│   │   ├── hegelian/
│   │   ├── utilitarian/
│   │   ├── stoic/
│   │   ├── aristotelian/
│   │   └── socratic/
│   ├── workflow-variants/          # NEU — Umbenannt von variants/
│   │   ├── no_tables/
│   │   │   ├── strategist.md
│   │   │   └── ...
│   │   ├── formal/
│   │   └── concise/
│   └── workflows/                  # NEU — Workflow-spezifische Prompts
│       └── dialectic/             # Umbenannt von dialectic/
│           ├── strategist.md
│           └── critic.md
└── argumentation-pattern-example.md  # Schema-Dokumentation
```

### 5.2 Migrationsskript

```bash
# Alte Variants → Neue Struktur
# profiles/prompts/variants/kantian/*      → profiles/prompts/argumentation-patterns/kantian/*
# profiles/prompts/variants/steiner/*      → profiles/prompts/argumentation-patterns/steiner/*
# profiles/prompts/variants/dialectic/*    → profiles/prompts/workflows/dialectic/*
```

### 5.3 Backwards-Kompatibilität

- `PromptTemplate.variant` bleibt als Feld erhalten, Referenz auf `workflow-variants`
- `RoleDefinition.argumentation_pattern` neues Feld, Referenz auf `argumentation-patterns`
- Bestehende Importe/Exports müssen beide Felder berücksichtigen

---

## 6. Beispiel: Prompt-Assembly in der Praxis

**Use Case:** Hegelsche Debatte, Stoic-Critic

```
1. Base (Argumentation: Hegel, Rolle: Critic):
   "Im Rahmen der Hegelschen Dialektik übernimmst du die Rolle des Kritikers.
    Identifiziere die Schwächen der vorliegenden These und formuliere eine
    überzeugende Antithesse."

2. Layer (Workflow-Variante: "no_tables"):
   "Antworte ausschließlich im Fließtext. Verwende keine Tabellen oder Aufzählungen."

3. Layer (Tone Profile: akademisch):
   "Der Ton soll akademisch und analytisch sein."

= Finaler Prompt:
"Im Rahmen der Hegelschen Dialektik übernimmst du die Rolle des Kritikers.
 Identifiziere die Schwächen der vorliegenden These und formuliere eine
 überzeugende Antithesse. Antworte ausschließlich im Fließtext.
 Der Ton soll akademisch und analytisch sein."
```

---

## 7. Beispiel: Neue Workflow-Pipeline

### Interview-Workflow

```
wf-input → wf-strategist[mode:interviewer] → wf-analyst[mode:interviewer] → wf-moderator → wf-complete
```

- **Strategist** im Interviewer-Modus: Erstellt strukturierte Nachfragen statt Thesen
- **Analyst** im Interviewer-Modus: Vertieft spezifische Aspekte, hakt nach
- **Moderator**: Zusammenfassung der gewonnenen Erkenntnisse

### Streitgespräch

```
wf-input → wf-strategist[mode:advocate] → wf-critic[mode:adversary] → wf-moderator[mode:referee] → wf-complete
```

- **Strategist** als Advocate: Verteidigt eine Position einseitig
- **Critic** als Adversary: Aktive Konfrontation, Widerlegung
- **Moderator** als Referee: Regeln-Durchsetzen, Fairness bewerten

---

## 8. Veraltete Konzepte

### 8.1 Entfernung / Umbenennung

| Alt | Neu | Status |
|---|---|---|
| `prompts/variants/kantian/` | `prompts/argumentation-patterns/kantian/` | Umbenennen |
| `prompts/variants/steiner/` | `prompts/argumentation-patterns/steiner/` | Umbenennen |
| `prompts/variants/dialectic/` | `prompts/workflows/dialectic/` | Umbenennen + Template |
| `role: "stoic"` in Agent-Persona | `argumentation_pattern: "stoic"` in RoleDefinition | Migration |
| `role: "german-law"` in Agent-Persona | `argumentation_pattern: "german-law"` oder eigenes Pattern | Evaluierung |

### 8.2 Abwärtskompatibilität

- Bestehende `role`-Felder in `AgentPersona` (Legacy) müssen weiterhin funktionieren
- `RoleDefinition.role_type_id` bleibt primäres Feld; `mode` und `argumentation_pattern` sind optionale Ergänzungen
- Alte Prompts ohne `argumentation_pattern` bekommen einen Default-Wert `"default"`
- `moderator_node_factory` bleibt als Sonderfall erhalten (Consensus-Berechnung)

---

## 9. Testplan

### 9.1 Unit-Tests (Backend)

| Test | Datei |
|---|---|
| Neue `role_type_id`-Werte validieren | `tests/backend/test_workflow_graph_models.py` |
| `ArgumentationPattern`-Lookup | `tests/backend/test_workflow_compiler.py` |
| Prompt-Assembly mit Pattern | `tests/backend/test_workflow_compiler.py` |
| RoleDefinition mit `mode` und `argumentation_pattern` | `tests/backend/test_blueprints.py` |
| Compiler validiert neue Node-Typen | `tests/backend/test_workflow_compiler.py` |
| Abwärtskompatibilität alter Prompts | `tests/backend/test_profiles.py` |

### 9.2 Frontend-Tests

| Test | Datei |
|---|---|
| Neue Node-Typen registrieren sich | `frontend/tests/unit/workflow/mapper.test.js` |
| WorkflowNodeForm zeigt neue Felder | Manuell / Playwright |
| Palette zeigt neue Nodes | `frontend/tests/e2e/*.spec.ts` |
| Drag & Drop neuer Nodes | `frontend/tests/e2e/*.spec.ts` |

---

## 10. Abhängigkeiten & Reihenfolge

```
Phase 1: Datenmodell & Migration
  ├── 1.1  RoleType.category-Feld hinzufügen (models.py, migration)
  ├── 1.2  RoleDefinition.argumentation_pattern-Feld hinzufügen (models.py, migration)
  ├── 1.3  AGENT_NODE_TYPES / WORKFLOW_NODE_TYPES erweitern (workload_models.py)
  └── 1.4  Neue Prompts anlegen (argumentation-patterns/)

Phase 2: Backend-Logik
  ├── 2.1  Prompt-Service erweitern (argumentation_pattern-Logik)
  ├── 2.2  Compiler-Service aktualisieren (neue Felder, Validierung)
  ├── 2.3  WorkflowCompiler aktualisieren (AGENT_NODE_TYPES)
  ├── 2.4  Node Functions: Prompt-Assembly-Pipeline implementieren
  ├── 2.5  Repository: argumentation_pattern-Methoden
  └── 2.6  API-Endpunkte: argumentation_patterns-Router

Phase 3: Frontend
  ├── 3.1  Neue Node-Komponenten erstellen (FactChecker, Analyst, Creative)
  ├── 3.2  Registry: Neue Nodes registrieren
  ├── 3.3  WorkflowNodeForm: Neue Felder (argumentation_pattern, mode)
  ├── 3.4  Store: nodeTypeMap erweitern
  ├── 3.5  Palette: Neue Workflow-Nodes anzeigen
  └── 3.6  Mapping-Schicht aktualisieren

Phase 4: Workflow-Templates
  ├── 4.1  "Hegelsche Dialektik" als System-Template
  ├── 4.2  "Interview" als System-Template
  ├── 4.3  "Streitgespräch" als System-Template
  └── 4.4  "Mediation" als System-Template

Phase 5: Migration & Cleanup
  ├── 5.1  Migrationsskript für alte Variants → neue Struktur
  ├── 5.2  Alte Prompts/variants/-Directory deprecated markieren
  ├── 5.3  Abwärtskompatibilitäts-Layer für Legacy-Daten
  └── 5.4  Dokumentation aktualisieren (user_manual, technical_doc)
```

---

## 11. Risiken & Hinweise

| Risiko | Auswirkung | Mitigation |
|---|---|---|
| Breaking-Change bei Prompt-Varianten | Bestehende Workflows zeigen falsche Prompts | Abwärtskompatibilität: Fallback auf `default` wenn Pattern nicht gefunden |
| Zu viele Node-Typen im Literal | Wartungsaufwand steigt | Generischen `agent_node_factory` beibehalten; neue Rollen primär über `role_type_id` |
| Formatorische Modi werden nicht verstanden | UX-Verwirrung | Klare Tooltips im Frontend: "Modus ändert die Gesprächsform, nicht die Funktion" |
| Datenbankmigration schlägt fehl | Produktivdaten betroffen | Migration als optionales Feature mit Rollback; Test auf Kopie |

---

## 12. Akzeptanzkriterien

- [x] **AC-1:** Neue funktionale Rollen (`fact-checker`, `analyst`, `creative`) sind als `role_type_id` in `RoleType` anlegbar
- [x] **AC-2:** Neue Rollen erscheinen als eigene Node-Typen im Workflow Canvas (`wf-fact-checker`, `wf-analyst`, `wf-creative`)
- [x] **AC-3:** Formatorische Modi (`interviewer`, `advocate`, `adversary`, `mediator`, `referee`) sind als `mode`-Feld in `RoleDefinition` verfügbar
- [x] **AC-4:** Argumentationsmuster (`kantian`, `hegelian`, `utilitarian`, `stoic`, `aristotelian`, `socratic`) sind als `argumentation_pattern` auf `RoleDefinition` verfügbar
- [x] **AC-5:** Prompt-Assembly liefert den korrekten zusammengesetzten System-Prompt (Argumentation + Rolle + Variante + Tone)
- [ ] **AC-6:** Alte Prompts (`variants/kantian/*`, `variants/dialectic/*`, `variants/steiner/*`) sind migriert oder veraltet markiert
- [x] **AC-7:** Workflow-Templates "Interview", "Streitgespräch" und "Mediation" sind als System-Templates verfügbar (Hegelsche Dialektik bereits vorhanden)
- [ ] **AC-8:** Abwärtskompatibilität: Bestehende Blueprints und Workflows funktionieren unverändert
- [x] **AC-9:** Alle neuen Node-Typen sind im Frontend als draggable Nodes im Workflow-Modus nutzbar
- [ ] **AC-10:** Unit-Tests und Integrationstests für alle neuen Pfade vorhanden
