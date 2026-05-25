---
name: kitsune-bundle-workflow-builder
description: Bauen und Editieren von Agent-Bundles und Workflow-Templates in Danwa. Verwende diese Skill immer, wenn Kitsune (der Danwa-KI-Assistent) Bundles oder Workflows erstellen, editieren oder erweitern soll — egal ob der User explizit "Bundle", "Workflow", "Template" sagt oder nur "neue Rolle hinzufügen", "Debatten-Vorlage bauen", "Phase einfügen". Die Skill deckt den gesamten Prozess ab: von der Bundle-Komposition (agent-core + argumentation-pattern + prompt-modifier) über das Template-Layout (wf-phase/wf-agent/wf-gate) bis zur Canvas-Integration.
---

# Kitsune Bundle & Workflow Builder

Du assistierst beim Erstellen und Editieren von **Agent-Bundles** und **Workflow-Templates** in Danwa. Deine Aufgabe ist es, den User Schritt für Schritt durch den Bauprozess zu führen — oder direkt zu handeln, wenn der User sagt, was er braucht.

## Architekturverständnis

Danwa hat zwei Modulebenen, die zusammenarbeiten:

1. **Agent Bundles** (`modules/agent-bundles/`): Fassen einen agent-core + argumentation-pattern + prompt-modifier zu einer einsatzbereiten Rolle zusammen. Bundles erscheinen im "Agent Bundles"-Tab und können per Drag & Drop auf die Canvas gezogen werden (werden zu `wf-agent`-Knoten).

2. **Workflow Templates** (`modules/workflows/`): Definieren eine komplette Debattenstruktur mit Phasen, Agenten, Gates und Edges. Templates erscheinen im Template-Gallery-Dialog und werden per "Instantiate" zu einem ausführbaren Workflow.

## Bundle erstellen

### 1. Rolle identifizieren

Frage den User nach:
- **Rollenname** (z.B. "Data Scientist", "UX Researcher")
- **Welcher agent-core** soll verwendet werden? (Lies `modules/agent-cores/` für verfügbare Cores)
- **Soll ein neuer agent-core erstellt werden** oder reicht ein existierender?
- **argumentation-pattern** (default: `"strategist"`, es sei denn die Rolle braucht ein spezifisches)
- **prompt-modifier** (default: `"prompt-modifier-neutral-default"`)

### 2. Ordner anlegen

```
modules/agent-bundles/bundle-{role}/
├── manifest.json
└── profile.json
```

### 3. manifest.json schreiben

```json
{
  "schema_version": "2.0.0",
  "module_id": "bundle-{role}",
  "name": { "en": "{Role Display Name}" },
  "description": { "en": "Description of this bundle." },
  "version": "1.0.0",
  "type": "bundle",
  "category": "bundles",
  "author": { "name": "Danwa Community" },
  "license": "CC-BY-4.0",
  "tags": ["{tag1}", "{tag2}"],
  "language": "en",
  "profile_file": "profile.json",
  "profile_format": "json",
  "dependencies": {
    "agent-cores/{agent-core-id}": ">=1.0.0"
  }
}
```

Regeln:
- `type` MUSS `"bundle"` sein
- `category` MUSS `"bundles"` sein
- `module_id` MUSS mit `"bundle-"` beginnen
- `profile_format` MUSS `"json"` sein
- `dependencies` mapped `agent-cores/{id}` → Version

### 4. profile.json schreiben

```json
{
  "id": "bundle-{role}",
  "name": "{Role Display Name}",
  "description": "Description.",
  "llm_profile_id": "default",
  "role_type_id": "{role-type}",
  "composition": {
    "agent_core_id": "{agent-core-id}",
    "argumentation_pattern_id": "{pattern-id}",
    "prompt_modifier_id": "prompt-modifier-neutral-default"
  },
  "is_active": true
}
```

`role_type_id` ist der Rollen-Identifier (z.B. `analyst`, `creative-thinker`). Er sollte sprechend zur Rolle sein — verwende nicht `_resolve_role_type_id` (der Composer nimmt `parts[0]`, was bei `creative-thinker-default` fälschlich `creative` ergäbe). Für Dateisystem-Bundles wird der Wert aus profile.json 1:1 übernommen.

Für detaillierte Schemadefinitionen lies `references/bundle-schema.md`.

## Bundle editieren

Lies die bestehenden Dateien unter `modules/agent-bundles/bundle-{role}/`, passe Werte an:
- `name`/`description` in manifest.json und profile.json synchron halten
- `composition`-Referenzen aktualisieren, wenn sich agent-core oder pattern ändert
- `tags` erweitern/reduzieren

## Workflow-Template erstellen

### 1. Anforderungen klären

Frage den User nach:
- **Wie viele Phasen?** Welches Ziel hat jede Phase?
- **Welche Agenten pro Phase?** Welche Bundles?
- **Soll es Platzhalter geben** (User wählt Agent-Blueprints bei Instantierung) oder **konkrete Bundles** (Bundles sind immer verfügbar)?
- **Terminierung**: Nach max Runden? Bei Konsens? Beides?

### 2. Struktur planen

Eine typische Mehr-Phasen-Debatte:

```
Phase 1: Analyse
  → analyst, creative-thinker, socratic-questioner
Phase 2: Strategie
  → strategist, expert-reviewer, steel-manner
Phase 3: Kontroverse
  → devils-advocate, fact-checker, troll
Phase 4: Synthese
  → mediator, ethicist, synthesizer
Phase 5: Abschluss
  → moderator, critic, optimizer
```

Zwischen Phasen: gate (prüft Phasenziele) → nächste Phase.

### 3. Ordner anlegen

```
modules/workflows/workflow-tpl-{name}/
├── manifest.json
└── profile.json
```

### 4. manifest.json schreiben

```json
{
  "schema_version": "2.0.0",
  "module_id": "workflow-tpl-{name}",
  "name": { "en": "Template Name" },
  "version": "1.0.0",
  "type": "workflow-template",
  "category": "workflows",
  "profile_file": "profile.json",
  "profile_format": "json",
  "files": []
}
```

### 5. profile.json mit template_data schreiben

Die `template_data.nodes` enthalten alle Knoten:

**Phase-Container:**
```json
{
  "id": "phase-1",
  "type": "wf-phase",
  "label": "Phase 1: {Name}",
  "position": { "x": 0, "y": 0 },
  "config": {
    "name": "{Name}",
    "max_rounds": 3,
    "objective": "Phase objective"
  }
}
```

**Agenten** (mit `parent_id` auf Phase) — `bundle_id`, `parent_id` und `label` MÜSSEN auf oberster Node-Ebene stehen, NIEMALS in `config`:
```json
{
  "id": "{role}-1",
  "type": "wf-agent",
  "label": "{Role}",
  "bundle_id": "bundle-{role}",
  "parent_id": "phase-1",
  "position": { "x": 300, "y": 80 }
}
```
⚠️ **Achtung**: `bundle_id` gehört auf die oberste Ebene, nicht in `config.bundle_id`. Das WorkflowNode-Modell erwartet `bundle_id` als direktes Feld. Ein `config.bundle_id` wird beim Parsen ignoriert.

**Input/Gate/Output:**
```json
{ "id": "input-1", "type": "wf-input", "label": "Topic Input", "position": { "x": 100, "y": 200 } },
{ "id": "init-1", "type": "wf-initialize", "label": "Initialize", "position": { "x": 350, "y": 200 } },
{ "id": "gate-1", "type": "wf-gate", "label": "Phase 1 Complete?", "position": { "x": 1200, "y": 150 },
  "config": { "condition": "phase_1_objective_met" } },
{ "id": "output-1", "type": "wf-output", "label": "Final Output", "position": { "x": 1600, "y": 200 } }
```

**Edges** verbinden die Knoten:
```json
{
  "id": "e1", "source": "input-1", "target": "init-1", "type": "sequential"
}
```

Edge-Typen nach Situation:
| Situation | Edge-Typ |
|---|---|
| Normale Flussrichtung (input→init, init→agent, agent→gate) | `sequential` |
| Gate → Agenten (nächste Runde innerhalb Phase) | `feedback` |
| Gate → nächste Phase oder Output (Bedingung erfüllt) | `conditional` |
| User greift ein | `interjection` |

**⚠️ Wichtig: Gate→Phase/Output IMMER `conditional`, nie `sequential`.** Ein `sequential` Edge von Gate zu Phase würde die Bedinungsprüfung überspringen. Beispiel:
```json
{ "id": "e-gate1-phase2", "source": "gate-1", "target": "phase-2", "type": "conditional" }
```

**Vollständiges Multi-Phase Edge-Pattern:**
```
input → init                          (sequential)
init → phase-1-agent-1, agent-2      (sequential, parallele Agents in Phase)
agent-1, agent-2 → gate-1             (sequential, Agents → Gate)
gate-1 → agent-1, agent-2             (feedback, nächste Runde in Phase)
gate-1 → phase-2                      (conditional, Phasenübergang)
phase-2 → agent-3, agent-4            (sequential)
agent-3, agent-4 → gate-2             (sequential)
gate-2 → agent-3, agent-4             (feedback)
gate-2 → phase-3                      (conditional)
phase-3 → agent-5, agent-6            (sequential)
agent-5, agent-6 → gate-3             (sequential)
gate-3 → agent-5, agent-6             (feedback)
gate-3 → output                       (conditional, finale Ausgabe)
```

**Termination Conditions:**
```json
"termination_conditions": [
  { "type": "max_rounds", "value": 5, "description": "Maximum rounds" },
  { "type": "consensus_reached", "value": 0.9, "description": "Consensus threshold" }
]
```

**Entry Point:**
```json
"entry_point": "input-1"
```

Für vollständige Schemadetails lies `references/template-schema.md`.

### 6. Platzhalter (optional)

Falls die Template-Struktur es erlaubt, dass der User bei Instantierung eigene Blueprints wählt:

```json
"placeholders": [
  {
    "key": "strategist_blueprint_id",
    "type": "blueprint_ref",
    "description": "Agent Blueprint for the Strategist role"
  },
  {
    "key": "max_rounds",
    "type": "integer",
    "default": 5,
    "description": "Maximum debate rounds"
  }
]
```

Verwende `{{key}}` in den entsprechenden `agent_blueprint_id`-Feldern der nodes.

**Wann Platzhalter, wann konkrete bundle_id?**
- **Konkrete bundle_id**: Bundle existiert als Dateisystem-Modul → immer verfügbar → direkt referenzieren
- **Platzhalter `{{...}}`**: User soll bei Instantierung einen Wert wählen (Blueprint-Ref, Zahl, String)

## Workflow-Template editieren

Lies bestehende `modules/workflows/workflow-tpl-{name}/profile.json`, passe `template_data.nodes`, `.edges`, `.termination_conditions` an. Achte darauf, dass:
- Alle node `id`s sind eindeutig (auch über verschiedene Templates hinweg ist das nicht nötig, aber innerhalb eines Templates müssen sie eindeutig sein)
- Jede Edge `source` und `target` auf existierende node-IDs verweist
- Bei Phasen-Änderungen die `parent_id` der Agenten aktualisiert wird

## Canvas-Integration (wie Bundles auf der Canvas landen)

Bundles werden automatisch im "Agent Bundles"-Tab angezeigt. Wenn ein User ein Bundle auf die Canvas zieht, passiert folgendes:

1. `BlueprintCanvas.handleDrop` empfängt den Drop mit `nodeType = 'agent-bundle'`
2. Die Entity-ID wird aus den Drop-Daten gelesen (z.B. `"bundle-analyst"`)
3. Die API `getAgentBundle(entityId)` lädt die Bundle-Daten
4. Ein neuer `wf-agent`-Knoten wird erstellt mit `data.bundle_id = entityId`
5. Der Knoten erscheint auf der Canvas und kann mit anderen Knoten verbunden werden

Du musst nichts zusätzlich tun — deine erstellten Bundles erscheinen automatisch im Tab und können per Drag & Drop genutzt werden.

## Validierung vor Abschluss

Bevor du ein Bundle oder Template als fertig meldest, prüfe:

**Bundle:**
- manifest.json: `type: "bundle"`, `category: "bundles"`, `profile_format: "json"`
- profile.json: `role_type_id` zum Rollennamen passend (nicht `parts[0]` des agent-core)
- Alle referenzierten Module (agent-core, argumentation-pattern, prompt-modifier) existieren als Dateisystem-Module

**Template:**
- Alle node-IDs sind eindeutig
- `entry_point` zeigt auf eine existierende node-ID
- termination_conditions haben korrekte Typen
- Bei `wf-gate`-Knoten: `config.condition` ist gesetzt
- `bundle_id`, `parent_id`, `label` auf oberster Node-Ebene (nie in `config`)
- Gate→Phase/Output Edges haben `type: "conditional"` (nie `"sequential"`)
- Bei `{{placeholders}}`: passender Eintrag in `placeholders[]`
- Edges verbinden nur existierende Knoten
- Phase-Container sind breit genug für ihre Agenten (min ~700px)

## Beispiele

Lies bestehende Templates für Referenz:
- `modules/workflows/workflow-tpl-standard-debate/profile.json` — einfache Debatte mit 4 Agenten + moderator + feedback-loop
- `modules/workflows/workflow-tpl-dialectic-debate/profile.json` — Debatte mit gate + conditional edges
- Bestehende Bundles unter `modules/agent-bundles/` für Bundle-Struktur
