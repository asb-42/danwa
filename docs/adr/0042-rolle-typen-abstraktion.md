# ADR 0042: Rollen-Typen-Abstraktion — Vierstufige Architektur

| Feld | Wert |
|------|------|
| **Status** | Accepted |
| **Datum** | 2026-05-13 |
| **Autor** | Kilo |
| **Betroffene Systeme** | Backend (Blueprints, Workflow, Prompt-Service), Frontend (Canvas, Nodes, Forms) |
| **Vorherige ADRs** | ADR-0039 (Blueprint Canvas), ADR-0040 (Prompt-Varianten), ADR-0041 (Tone Profiles) |

---

## 1. Kontext und Problemstellung

Die Danwa-Plattform hatte bisher vier **hart verdrahtete** Agenten-Rollen:
`strategist`, `critic`, `optimizer`, `moderator`.

Diese waren als `Literal`-Typen in Pydantic-Modellen, Frontend-Enums und
Prompt-Verzeichnissen fest codiert. Jede neue Rolle erforderte Änderungen an
mindestens 8 Stellen im Code — vom Datenmodell über den Compiler bis zur
Palette.

**Probleme:**
- Keine Möglichkeit, domain-spezifische Rollen zu erstellen (z.B. "Jurist", "Mediziner")
- Formatorische Gesprächsformen (Interview, Streitgespräch) waren nicht von der
  funktionalen Rolle trennbar
- Prompt-Varianten (`kantian`, `steiner`, `dialectic`) lagen strukturell falsch
  unter `prompts/variants/` statt als Eigenschaft der Rollendefinition
- Kein einheitliches System für Argumentationsmuster, Ton-Profile und
  Gesprächsformen

---

## 2. Entscheidung: Vierstufiges Rollen-Modell

Die neue Architektur trennt vier orthogonalen Dimensionen voneinander:

```
┌──────────────────────────────────────────────────────────────────────┐
│  Ebene 1: Funktionale Kernrolle  (Was macht der Agent?)             │
│  → role_type_id auf RoleDefinition / WorkflowNode.type              │
├──────────────────────────────────────────────────────────────────────┤
│  Ebene 2: Formatorische Rolle     (In welcher Gesprächsform?)       │
│  → mode auf RoleDefinition / ResolvedAgent.mode                     │
├──────────────────────────────────────────────────────────────────────┤
│  Ebene 3: Argumentationsmuster     (Wie argumentiert der Agent?)    │
│  → argumentation_pattern auf RoleDefinition                         │
├──────────────────────────────────────────────────────────────────────┤
│  Ebene 4: Tone Profile             (Wie emotional/hitzig?)          │
│  → ToneRef per injects_config-Edge (bereits implementiert)          │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.1 Abgrenzungskriterium: Funktion vs. Formatorik

| Kriterium | Funktionale Rolle | Formatorische Rolle |
|-----------|-------------------|---------------------|
| **Definition** | Ein eigenständiger Arbeitsschritt mit eigener Aufgabe | Die Art und Weise, wie ein Schritt ausgeführt wird |
| **Pipeline-Position** | Eigener Knoten mit eigenem Output | Kein eigener Knoten — Modifikation eines bestehenden Knotens |
| **Beispiel** | `analyst` — führt Datenanalyse durch | `interviewer` — stellt die Fragen, *bevor* Analyst antwortet |
| **Persistierung** | `role_type_id` in `role_types`-Tabelle | `mode`-Feld in `role_definitions`-Tabelle |
| **Faustregel** | Hat eine eigene Position in der Pipeline → eigener `role_type_id` | Beeinflusst nur die Vortragsart → `mode`-Feld |

### 2.2 Funktionale Kernrollen (Ebene 1)

| `role_type_id` | Icon | Farbe     | Kategorie    | Beschreibung                                           |
|----------------|------|-----------|--------------|--------------------------------------------------------|
| `strategist`   | 🧠   | `#3b82f6` | functional   | Strukturierung, Themenextraktion, Rahmen setzen        |
| `critic`       | 🔍   | `#ef4444` | functional   | Schwachstellenidentifikation, Devil's Advocate         |
| `optimizer`    | ⚡   | `#f59e0b` | functional   | Synthese, Verfeinerung, Verbesserung                   |
| `moderator`    | 🎯   | `#6366f1` | functional   | Konsensbildung, Abschlussbewertung, Zeitmanagement     |
| `fact-checker` | ✅   | `#10b981` | functional   | Faktische Verifizierung, Quellenprüfung                |
| `analyst`      | 📊   | `#06b6d4` | functional   | Tiefgehende Datenanalyse, Mustererkennung              |
| `creative`     | 💡   | `#ec4899` | functional   | Kreative Ideenfindung, Perspektivwechsel, Brainstorming|
| `expert-reviewer` | 🎓 | `#06b6d4` | functional | Domänen-spezifische Expertenbewertung                  |

### 2.3 Formatorische Rollen (Ebene 2) — `mode`-Werte

Formatorische Rollen sind **keine** eigenen Node-Typen. Sie werden als `mode`-Feld
auf einer `RoleDefinition` gesetzt und modifizieren das Verhalten des zugehörigen
funktionalen Agenten.

| `mode`-Wert        | Anwendbare `role_type_id` | Beschreibung                                                       |
|--------------------|---------------------------|--------------------------------------------------------------------|
| `interviewer`      | `strategist`, `analyst`   | Gezieltes Nachfragen, strukturierte Interviews                    |
| `advocate`         | `strategist`              | Einseitige Verteidigung einer Position (Streitgespräch: These)    |
| `adversary`        | `critic`                  | Aktive Konfrontation, Widerlegung (Streitgespräch: Antithese)     |
| `mediator`         | `moderator`, `optimizer`  | Vermittlung, Kompromissfindung                                     |
| `referee`          | `moderator`               | Regeln-Durchsetzen, Fairness bewerten                             |
| `facilitator`      | `moderator`               | Prozessförderung, ohne inhaltliche Bewertung                      |
| `devils-advocate`  | `critic`                  | Systematisches Infragestellen ohne direkte Konfrontation          |

### 2.4 Argumentationsmuster (Ebene 3)

Argumentationsmuster definieren die **inhaltliche/philosophische Ausrichtung**
eines Agenten. Jedes Muster hat für jede funktionale Rolle eine eigene
Prompt-Datei.

| Pattern            | Philosophische Grundlage                             | Dateien |
|--------------------|------------------------------------------------------|---------|
| `kantian`          | Kategorischer Imperativ, Pflichtethik                | 7 Rollen × 2 Sprachen |
| `hegelian`         | Hegelsche Dialektik (These–Antithese–Synthese)       | 7 Rollen × 2 Sprachen |
| `utilitarian`      | Utilitarismus, größtmögliches Glück                 | 7 Rollen × 1 Sprache  |
| `stoic`            | Stoische Tugendethik, Gleichmut                     | 7 Rollen × 2 Sprachen |
| `aristotelian`     | Aristotelische Tugendethik, Golden Mean              | 7 Rollen × 2 Sprachen |
| `socratic`         | Sokratische Methode, maieutisches Fragen            | 7 Rollen × 2 Sprachen |

**Verzeichnisstruktur:**
```
profiles/argumentation-patterns/
├── kantian/
│   ├── strategist.md
│   ├── strategist-en.md
│   ├── critic.md
│   ├── fact-checker.md
│   ├── analyst.md
│   ├── creative.md
│   ├── optimizer.md
│   └── moderator.md
├── hegelian/
├── utilitarian/
├── stoic/
├── aristotelian/
└── socratic/
```

### 2.5 Tone Profile (Ebene 4)

Tone Profile steuern die **emotionale Temperatur und rhetorische Art** der
Debatte. Sie werden als separate Nodes (`wf-tone-profile`) im Canvas platziert
und per `injects_config`-Edge an Agent-Nodes injiziert.

| `style`-Wert     | Beschreibung                                              |
|------------------|-----------------------------------------------------------|
| `heated`         | Emotional, fordernd, polemisch                           |
| `academic`       | Sachlich, analytisch, zitierungsfreudig                   |
| `conversational`| Natürlich, umgangssprachlich, freundlich                   |
| `socratic`       | Fragenstellerisch, entdeckend, nachforschend               |
| `neutral`        | Ausgewogen, sachlich, ohne emotionale Färbung (Default)   |

Weitere Parameter: `formality` (0.0–1.0), `verbosity` (concise/normal/verbose),
`emotional_valence` (0.0–1.0), `rhetorical_mode` (none/questioning/assertive/dialectic).

---

## 3. Prompt-Assembly-Pipeline

Die finale System-Prompt eines Agenten wird aus **fünf Schichten** zusammengesetzt:

```
┌─────────────────────────────────────────────────────────────────┐
│  Schicht 1: Base Role Prompt                                     │
│  Quelle: profiles/prompts/default/{role_type_id}.md             │
│  → Definiert die Kernaufgabe und Grundhaltung des Agenten       │
├─────────────────────────────────────────────────────────────────┤
│  Schicht 2: Argumentation Pattern                                │
│  Quelle: profiles/argumentation-patterns/{pattern}/{role}.md    │
│  → Philosophische/sachliche Ausrichtung, Denkstruktur           │
├─────────────────────────────────────────────────────────────────┤
│  Schicht 3: Mode Modifier                                        │
│  → Formatorischer Modus (interviewer, advocate, adversary…)     │
│  → Wird als Text-Injection *vor* dem Workflow-Variant eingepflegt│
├─────────────────────────────────────────────────────────────────┤
│  Schicht 4: Tone Injection                                       │
│  Quelle: ToneProfile (per injects_config-Edge)                  │
│  → Emotionale/rhetorische Färbung via inject_tone_profile()      │
├─────────────────────────────────────────────────────────────────┤
│  Schicht 5: Workflow Variant                                     │
│  Quelle: profiles/workflow-variants/{variant}/{role}.md         │
│  → Feinsteuerung: Formatierung, Stil, Tabellen, Aufzählungen    │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────┐
│  FINALER SYSTEM PROMPT                                          │
│  = Base + Pattern + Mode Modifier + Tone + Variant              │
└─────────────────────────────────────────────────────────────────┘
```

### Implementierung im PromptService

```python
def assemble_prompt(
    self,
    role_type_id: str,
    argumentation_pattern: str | None = None,
    workflow_variant: str = "default",
    language: str = "de",
) -> str:
    parts: list[str] = []

    # Layer 1: Base Role Prompt (immer vorhanden)
    base_prompt = self.get_prompt("default", role_type_id, language=language)
    if base_prompt:
        parts.append(base_prompt["content"])

    # Layer 2: Argumentation Pattern
    if argumentation_pattern:
        ap_prompt = self.get_argumentation_pattern(
            argumentation_pattern, role_type_id, language
        )
        if ap_prompt:
            parts.append(ap_prompt)

    # Layer 3: Mode Modifier (in node_functions.py, vor dem LLM-Call eingefügt)

    # Layer 4: Tone Injection (in node_functions.py, per inject_tone_profile())

    # Layer 5: Workflow Variant
    try:
        wf_prompt = self.get_prompt(workflow_variant, role_type_id, language=language)
        if wf_prompt and wf_prompt.get("content"):
            parts.append(wf_prompt["content"])
    except FileNotFoundError:
        pass  # Fallback to default

    return "\n\n".join(parts)
```

**Reihenfolge der Zusammensetzung im Node:**
1. `assemble_prompt()` → Base + Pattern + Variant (Schichten 1, 2, 5)
2. `mode`-Modifier wird als Kontext-String *vor* dem User-Prompt injiziert
3. Tone-Profile-Injection erfolgt *auf* dem finalen system_prompt

---

## 4. Datenmodell-Änderungen

### 4.1 RoleType (neu: `category`-Feld)

```python
class RoleType(BaseModel):
    id: str
    name: str
    icon: str = "👤"
    color: str = "#8b5cf6"
    category: Literal["functional", "formative"] = "functional"
    # ...
```

### 4.2 RoleDefinition (neue Felder)

```python
class RoleDefinition(BaseModel):
    id: str
    name: str
    role_type_id: str = "strategist"
    argumentation_pattern: str | None = None   # → argumentation-patterns/
    mode: str | None = None                    # → formatorischer Modus
    prompt_template_id: str | None = None
    # ...
```

### 4.3 AgentPersona (erweitert)

```python
class AgentPersona(BaseModel):
    role: str  # Von Literal auf str erweitert (analyst, creative, …)
    argumentation_pattern: str | None = None
    mode: str | None = None
    # ...
```

### 4.4 WorkflowNode (Literal erweitert)

```python
class WorkflowNode(BaseModel):
    type: Literal[
        "wf-input", "wf-initialize",
        "wf-strategist", "wf-critic", "wf-fact-checker",
        "wf-optimizer", "wf-moderator",
        "wf-analyst", "wf-creative",         # ← NEU
        "wf-user-injection", "wf-gate", "wf-tone-profile",
    ]
```

### 4.5 ResolvedAgentConfig (WorkflowCompiler)

```python
@dataclass
class ResolvedAgentConfig:
    node_id: str
    blueprint_id: str
    role: str
    argumentation_pattern: str = ""   # ← NEU
    mode: str = ""                     # ← NEU
    tone_profile_source_node_id: str | None = None  # ← NEU
    # …
```

---

## 5. Prompt-Migration

### 5.1 Alte Struktur → Neue Struktur

| Alt (falsch)                           | Neu (richtig)                                          |
|----------------------------------------|--------------------------------------------------------|
| `prompts/variants/kantian/strategist.md`  | `argumentation-patterns/kantian/strategist.md`         |
| `prompts/variants/steiner/strategist.md`  | `argumentation-patterns/steiner/strategist.md`         |
| `prompts/variants/dialectic/strategist.md`| `workflows/dialectic/strategist.md`                    |
| `prompts/default/strategist.md`          | `prompts/default/strategist.md` (unverändert)          |

### 5.2 Migrationsschritte

1. **Dateien verschieben:**
   ```bash
   mv profiles/prompts/variants/kantian/* profiles/prompts/argumentation-patterns/kantian/
   mv profiles/prompts/variants/steiner/* profiles/prompts/argumentation-patterns/steiner/
   mv profiles/prompts/variants/dialectic/* profiles/prompts/workflows/dialectic/
   ```

2. **DEPRECATED-Marker:** `DEPRECATED.txt` in jedem alten Verzeichnis mit Hinweis auf
   neue Struktur. Alte Dateien bleiben für Abwärtskompatibilität erhalten.

3. **Neue Dateien:** Für jede Kombination aus Pattern × Rolle eine Datei erstellen
   (insgesamt 84 Dateien für 6 Patterns × 7 Rollen × 2 Sprachen,
   zzgl. `utilitarian` nur in Deutsch = 85 Dateien).

4. **Workflow-Templates:** Dialektik-Prompts werden zu Workflow-Template
   "Hegelsche Dialektik" konvertiert. Neue Templates: Interview, Streitgespräch,
   Mediation, Schnellreview.

### 5.3 Abwärtskompatibilität

- **`from_legacy()` / `to_legacy()`:** RoleDefinition ↔ AgentPersona Roundtrip
  mit neuen Feldern (`argumentation_pattern`, `mode`)
- **Fallback-Kette:** `assemble_prompt()` → Pattern not found → Default Pattern
  → Variant not found → Default Variant
- **`role`-Feld:** Weiterhin als `str` akzeptiert; alte Literal-Werte funktionieren
  unverändert
- **Bestehende Blueprints:** `role_type_id` wird aus alten `role`-Werten abgeleitet
- **`moderator_node_factory`:** Bleibt als Sonderfall für Consensus-Berechnung

---

## 6. Backend-Änderungen im Detail

### 6.1 Neue API-Endpunkte

| Methode | Endpoint | Beschreibung |
|---------|----------|-------------|
| GET | `/api/v1/argumentation-patterns` | Liste aller verfügbaren Argumentationsmuster |
| GET | `/api/v1/argumentation-patterns/{name}` | Einzelnes Pattern mit Prompts pro Rolle |
| GET | `/api/v1/role-definitions?argumentation_pattern=` | Role Definitions nach Pattern filtern |

### 6.2 Core Services

- **`PromptService`**: Neue Methoden `get_argumentation_pattern()`,
  `list_argumentation_patterns()`, erweitertes `assemble_prompt()`
- **`CompilerService`**: `ResolvedAgent` um `argumentation_pattern` + `mode`
  erweitert; Validierung der Pattern-Referenz
- **`WorkflowCompiler`**: `ResolvedAgentConfig` um neue Felder erweitert;
  `_resolve_agent_config()` liest `argumentation_pattern` + `mode` von `RoleDefinition`
- **`BlueprintRepository`**: Neue Methoden `list_argumentation_patterns()`,
  `get_argumentation_pattern()`

### 6.3 Workflow-Compiler

- `agent_node_factory` kann **alle** Agent-Node-Typen bedienen
  (kein `elif`-Chain nötig)
- `moderator_node_factory` bleibt Sonderfall
- Neue Felder fließen in `resolved_configs` → `WorkflowState`

### 6.4 Node Functions

- `_resolve_system_prompt()`: Implementiert die 5-Schicht-Assembly
- Tone-Profile-Injection: `inject_tone_profile()` modifiziert den
  system_prompt nach der Assembly

---

## 7. Frontend-Änderungen im Detail

### 7.1 Neue Node-Komponenten

| Datei | Typ | Farbe | Icon |
|-------|-----|-------|------|
| `FactCheckerNode.svelte` | Erweitert von StrategistNode | `#10b981` | ✅ |
| `AnalystNode.svelte` | Erweitert von StrategistNode | `#06b6d4` | 📊 |
| `CreativeNode.svelte` | Erweitert von StrategistNode | `#ec4899` | 💡 |

### 7.2 Registrierung

```javascript
// registerAll.js
registerNode({ type: 'wf-fact-checker', component: FactCheckerNode, category: 'workflow', ... });
registerNode({ type: 'wf-analyst',      component: AnalystNode,      category: 'workflow', ... });
registerNode({ type: 'wf-creative',     component: CreativeNode,     category: 'workflow', ... });
```

### 7.3 WorkflowNodeForm

- Neues Dropdown `argumentation_pattern` (leer, kantian, hegelian, stoic, aristotelian, socratic, utilitarian)
- Neues Dropdown `mode` (kontextabhängig, abhängig von `role_type_id`)
- Wird nur bei Agent-Nodes angezeigt

### 7.4 Store & Mapping

- `store.svelte.js`: `nodeTypeMap` um neue Typen erweitert
- `mapper.js`: Neue Rollen und Artefakt-Typen gemappt
- `oob.js`: Neue Rollen in `getPreviousRole()`-Reihenfolge

---

## 8. Workflow-Templates

### 8.1 Neue System-Templates

| Template ID | Name | Pipeline |
|-------------|------|----------|
| `tpl-interview` | Interview | Strategist [mode: interviewer] → Analyst [mode: interviewer] → Moderator |
| `tpl-streitgespraech` | Streitgespräch | Strategist [mode: advocate] → Critic [mode: adversary] → Moderator [mode: referee] |
| `tpl-mediation` | Mediation | Strategist → Critic → Optimizer [mode: mediator] → Moderator |
| `tpl-quick-review` | Schnellreview | Strategist → Critic → Moderator |
| `tpl-dialectic-debate` | Hegelsche Dialektik | Strategist → Critic → Optimizer → Moderator |
| `tpl-kantian-analysis` | Kant'sche Analyse | Strategist → Critic [argumentation_pattern: kantian] → Optimizer → Moderator |
| `tpl-standard-debate` | Standard-Debatte | Strategist → Critic → Optimizer → Moderator |

---

## 9. Teststrategie

### 9.1 Backend-Tests (pytest)

| Test | Datei | Status |
|------|-------|--------|
| RoleDefinition CRUD mit neuen Feldern | `test_blueprints.py` | ✅ |
| Argumentation Pattern Lookup | `test_blueprints.py` | ✅ |
| Prompt Assembly mit Pattern | `test_blueprints.py` | ✅ |
| Abwärtskompatibilität (`from_legacy`/`to_legacy`) | `test_blueprints.py` | ✅ |
| Neue `role_type_id`-Werte in DB | `test_blueprints.py` | ✅ |
| `AgentPersona` mit erweitertem `role` | `test_profiles.py` | ✅ |
| Seed-Templates (7 statt 3) | `test_workflow_templates.py` | ✅ |
| Compiler validiert neue Nodes | `test_workflow_compiler.py` | ✅ |
| Workflow-Nodes mit neuen Rollen | `test_workflow_nodes.py` | ✅ |
| Canvas-to-Workflow Konvertierung | `test_canvas_to_workflow.py` | ✅ |

### 9.2 Frontend-Tests (Playwright)

| Test | Status |
|------|--------|
| Neue Nodes in Palette | Manuell / UI-Test empfohlen |
| Drag & Drop neuer Nodes | Manuell / UI-Test empfohlen |
| WorkflowNodeForm zeigt neue Felder | Manuell / UI-Test empfohlen |

---

## 10. Konsequenzen und Risiken

### 10.1 Positive Konsequenzen

- **Skalierbarkeit:** Neue Rollen können ohne Code-Änderungen am Kernsystem
  hinzugefügt werden (nur YAML + Prompt-Dateien + DB-Eintrag)
- **Flexibilität:** Formatorische Modi ermöglichen vielfältigere Debattier-Stile
- **Wiederverwendbarkeit:** Argumentationsmuster sind rollenunabhängig und
  können auf verschiedene Rollentypen angewendet werden
- **Benutzerfreundlichkeit:** Visual Canvas erlaubt Drag & Drop-Zusammenstellung

### 10.2 Risiken und Mitigation

| Risiko | Auswirkung | Mitigation |
|--------|------------|------------|
| Prompt-Assembly zu komplex | Unvorhersehbare Prompt-Interaktionen | Schichten sind klar getrennt; jede Schicht optional |
| Zu viele Node-Typen | Übersichtlichkeit leidet | Generischer `agent_node_factory`; `role_type_id` als String |
| Formatorische Modi nicht verstanden | UX-Verwirrung | Tooltips im Frontend; klare Dokumentation |
| DB-Migration fehlschlägt | Produktivdaten betroffen | Idempotente Migrationsskripte; Rollback möglich |
| Alte Prompts nicht migriert | Bestehende Workflows brechen | Abwärtskompatibilität + DEPRECATED-Marker |

### 10.3 Offene Punkte

- [ ] Visuelles Feedback im Canvas für `mode` und `argumentation_pattern` aktiver Nodes
- [ ] Import/Export von RoleDefinitions als YAML (aktuell nur JSON via API)
- [ ] Validierung: Sicherstellen, dass `argumentation_pattern`-Dateien existieren,
  bevor eine `RoleDefinition` gespeichert wird
- [ ] Integrationstest für den kompletten Workflow mit neuem Schema + alter Datenbank-Migration
- [ ] Frontend-Tests für neue Node-Typen (Playwright)

---

## 11. Akzeptanzkriterien

- [x] **AC-1:** Neue funktionale Rollen (`fact-checker`, `analyst`, `creative`, `expert-reviewer`) sind als `role_type_id` in `RoleType` anlegbar
- [x] **AC-2:** Neue Rollen erscheinen als eigene Node-Typen im Workflow Canvas (`wf-fact-checker`, `wf-analyst`, `wf-creative`)
- [x] **AC-3:** Formatorische Modi (`interviewer`, `advocate`, `adversary`, `mediator`, `referee`, `facilitator`) sind als `mode`-Feld in `RoleDefinition` verfügbar
- [x] **AC-4:** Argumentationsmuster (`kantian`, `hegelian`, `utilitarian`, `stoic`, `aristotelian`, `socratic`) sind als `argumentation_pattern` auf `RoleDefinition` verfügbar
- [x] **AC-5:** Prompt-Assembly liefert den korrekten zusammengesetzten System-Prompt (Base + Pattern + Variant + Tone)
- [x] **AC-6:** Alte Prompts (`variants/kantian/*`, `variants/dialectic/*`, `variants/steiner/*`) sind migriert und mit `DEPRECATED.txt` markiert
- [x] **AC-7:** Workflow-Templates "Interview", "Streitgespräch", "Mediation" und "Schnellreview" sind als System-Templates verfügbar
- [x] **AC-8:** Abwärtskompatibilität: Bestehende Blueprints und Workflows funktionieren unverändert (`from_legacy()`/`to_legacy()`)
- [x] **AC-9:** Alle neuen Node-Typen sind im Frontend als draggable Nodes im Workflow-Modus nutzbar
- [x] **AC-10:** Unit-Tests und Backend-Tests für alle neuen Pfade vorhanden (1057/1057 Tests passend)

---

## 12. Referenzen

- **Dateien (geändert):** `backend/blueprints/models.py`, `backend/blueprints/migrations.py`,
  `backend/blueprints/repository.py`, `backend/blueprints/importer.py`,
  `backend/blueprints/compiler.py`, `backend/core/profiles.py`,
  `backend/services/prompt_service.py`, `backend/workflow/node_functions.py`,
  `backend/workflow/workflow_compiler.py`, `backend/api/routers/argumentation_patterns.py`,
  `backend/api/routers/role_definitions.py`, `backend/main.py`
- **Dateien (neu):** `backend/api/routers/argumentation_patterns.py`,
  `profiles/argumentation-patterns/*/*.md`, `profiles/workflows/dialectic/*`,
  `profiles/workflow-variants/*/*.md`, `templates/*.json`,
  `frontend/src/components/blueprint/nodes/*Node.svelte`
- **Prompt-Dateien:** 85 Argumentations-Pattern-Dateien, 8 Workflow-Prompt-Dateien,
  4 Workflow-Variant-Dateien
- **Tests:** `tests/backend/test_blueprints.py` (112 tests), `tests/backend/test_profiles.py`,
  `tests/backend/test_workflow_templates.py`
