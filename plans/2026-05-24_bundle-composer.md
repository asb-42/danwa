# Bundle Composer — Build → Bundle Composer

> **Datum**: 2026-05-24
> **Status**: Geplant
> **Branch**: `main`

## Ziel

Einen Bundle Composer unter **Build → Bundle Composer** bauen, der aus **5 Modul-Komponenten** (Agent Core, Argumentation Pattern, Tone Profile, Prompt Modifier, LLM Profile) ein `AgentBundle` zusammensetzt — gespeichert in der bestehenden `agent_bundles`-Tabelle. Export als reines Abhängigkeitsmodul (keine Duplikate/Redundanzen), importierbar auf anderen Systemen.

## Architektur

```
UI (5 Dropdowns + Preview + Save/Export)
  │
  ▼
BundleComposer API (bundle_composer.py)
  │
  ├── ComposerService.compose()  →  Prompt-Assembly aus Modul-Inhalten
  ├── BundleComposer.create()    →  Persistenz in DB + Modul-Import
  ├── BundleComposer.export()    →  modules/agent-bundles/<id>/manifest.json
  └── BundleComposer.import()    →  Einlesen aus modules/agent-bundles/<id>/
        │
        ▼
  BundleResolver.resolve()       →  Erweitert: erkennt composition-Feld
        │                         und nutzt ComposerService statt legacy-Pfad
        ▼
  WorkflowCompiler + Canvas      →  Bundle kann als wf-agent auf Canvas
```

## Datenmodell

### PromptModifier (neu)

```python
class PromptModifier(BaseModel):
    id: str
    name: str
    content: str           # Der Modifikator-Text (Markdown)
    description: str = ""
    is_system: bool = False
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
```

Tabelle: `prompt_modifiers`

### BundleComposition (neu)

```python
class BundleComposition(BaseModel):
    """Modul-Referenzen für die Composer-Assembly — KEINE Inline-Daten."""
    agent_core_id: str = ""
    argumentation_pattern_id: str = ""
    prompt_modifier_id: str = ""
```

### AgentBundle (erweitert)

```python
class AgentBundle(BaseModel):
    # ... bestehende Felder ...
    composition: BundleComposition | None = None
    # None = legacy bundle (RoleType/ RoleDefinition-basiert)
    # gesetzt = Composer-basiert (Modul-Referenzen)
```

Neue Spalte: `composition_json TEXT` in `agent_bundles`-Tabelle.

Die IDs in `BundleComposition` referenzieren **Modul-IDs** (aus `modules/`), nicht DB-Primärschlüssel — daher keine FK-Constraints.
> FUTURE: Dependency-Resolver von danwa-modules auf GitHub löst fehlende Module auf.

## Prompt-Assembly (ComposerService — existiert bereits)

### Componente → Quelle
| Komponente | Modul-Typ | Quelle |
|---|---|---|
| Agent Core | `agent-persona` | `modules/agent-cores/<id>/profile.md` (Inhalt = system_prompt) |
| Argumentation Pattern | `argumentation-pattern` | `modules/agent-argumentation-patterns/<id>/profile.md` (Inhalt) |
| Tone Profile | `tone-profile` | `modules/agent-tone-profiles/<id>/profile.md` oder DB |
| Prompt Modifier | `prompt-modifier` | `modules/prompt-modifiers/<id>/profile.md` (Inhalt) |
| LLM Profile | `llm-profile` | `modules/llm-profiles/<id>/profile.yaml` |

### Assembly-Reihenfolge
```
1. Agent Core (system_prompt)
2. Argumentation Pattern (mit ## Argumentation Approach)
3. Tone Profile (mit ## Communication Style)
4. Prompt Modifier (roher Text, ohne Header — enthält eigene Formatierung)
```

→ **LLM Profile wird NICHT in den Prompt konkateniert** — es definiert nur das Target-LLM für die API-Config.

## API-Endpunkte

| Method | Endpoint | Beschreibung |
|--------|----------|-------------|
| `GET` | `/api/v1/bundles/composer/components` | Alle verfügbaren Komponenten aus 5 Kategorien |
| `POST` | `/api/v1/bundles/composer/preview` | Preview des konkatenierten Prompts (live, ohne Persistenz) |
| `POST` | `/api/v1/bundles/composer` | Neues AgentBundle aus Composition erstellen |
| `GET` | `/api/v1/bundles/composer/{id}` | Bundle-Details + Preview |
| `PUT` | `/api/v1/bundles/composer/{id}` | Composition + Metadaten aktualisieren |
| `GET` | `/api/v1/bundles/composer/{id}/export` | Bundle als agent-bundle Modul exportieren |
| `POST` | `/api/v1/bundles/composer/import` | Bundle aus modules/agent-bundles/ importieren |
| `DELETE` | `/api/v1/bundles/composer/{id}` | Bundle löschen |

## Export-Format (keine Redundanz!)

```
modules/agent-bundles/<bundle-id>/
├── manifest.json
│   {
│     "schema_version": "2.0.0",
│     "module_id": "<bundle-id>",
│     "name": {"en": "...", "de": "..."},
│     "description": {"en": "...", "de": "..."},
│     "version": "1.0.0",
│     "type": "bundle",
│     "category": "bundles",
│     "profile_file": "profile.json",
│     "profile_format": "json",
│     "dependencies": {
│       "agent-cores/strategist-default": ">=1.0.0",
│       "agent-argumentation-patterns/dialectic-strategist": ">=1.0.0",
│       "agent-tone-profiles/neutral": ">=1.0.0",
│       "prompt-modifiers/format-verbose": ">=1.0.0",
│       "llm-profiles/llm-openrouter-claude-3.6-sonnet": ">=1.0.0"
│     }
│   }
└── profile.json
    {
      "id": "<bundle-id>",
      "name": "...",
      "description": "...",
      "llm_profile_id": "llm-openrouter-claude-3.6-sonnet",
      "role_type_id": "strategist",
      "tone_profile_id": null,
      "role_definition_id": null,
      "prompt_template_id": null,
      "composition": {
        "agent_core_id": "strategist-default",
        "argumentation_pattern_id": "dialectic-strategist",
        "prompt_modifier_id": "format-verbose"
      },
      "is_active": true
    }
```

> **Hinweis**: Dependencies werden nur deklariert, nicht inline kopiert. Bei Import auf einem anderen System müssen die Module separat installiert sein. Ein zukünftiger Resolver wird fehlende Dependencies automatisch von `github.com/danwa-modules` nachladen.

## BundleResolver Integration

In `BundleResolver.resolve()`, nach dem Laden aller Entities:
- Wenn `bundle.composition` gesetzt & nicht-leer → `ComposerService.compose(Composition(...))` → system_prompt
- Sonst → bestehender `_assemble_system_prompt()`-Pfad

## DB-Migration

- `SCHEMA_VERSION`: 26 → 27
- Neue Tabelle: `prompt_modifiers`
- Neue Spalte: `composition_json TEXT` auf `agent_bundles`
- Seed: Prompt-Modifier aus `modules/prompt-modifiers/` in DB importieren

## Frontend

### Route
`#/bundles/composer`

### Neue Dateien
- `frontend/src/views/BundleComposerView.svelte` — Haupt-View
- API-Funktionen in `frontend/src/lib/api.js`

### Sidebar
Build-Section, neuer Eintrag zwischen Canvas und Manage:
```javascript
{ id: 'bundles-composer', label: 'Bundle Composer', icon: '🧬', route: 'bundles/composer' },
```

### i18n
- `nav.bundleComposer`: "Bundle Composer" / deutsch
- `nav.bundles`: "Bundles" / "Bundles"

### UI-Layout
```
┌──────────────────────────────────────────────┐
│  Bundle Composer                            │
├────────────────────────┬─────────────────────┤
│  Configuration         │  Preview            │
│                        │                     │
│  Agent Core: [──▼──]    │  ┌─────────────┐    │
│  Arg. Pattern: [──▼──]  │  │ Konkat.     │    │
│  Tone Profile: [──▼──]  │  │ Prompt      │    │
│  Prompt Modif.: [──▼──] │  │ (live)      │    │
│  LLM Profile:  [──▼──]  │  └─────────────┘    │
│                        │                     │
│  Name: [___________]   │                     │
│  Desc: [___________]   │                     │
│                        │                     │
│  [💾 Speichern]         │                     │
│  [📦 Exportieren]       │                     │
│  [📂 Importieren]       │                     │
└────────────────────────┴─────────────────────┘
```

## Abhängigkeiten

### Neu
- `PromptModifier` Modell + Tabelle
- `BundleComposition` Modell
- `BundleComposer` Service-Klasse
- `bundle_composer.py` API-Router
- `BundleComposerView.svelte`

### Bestehend (wird erweitert)
- `AgentBundle` (composition-Feld)
- `BundleResolver.resolve()` (Composer-Pfad)
- `ComposerService` (Preview-Endpunkt nutzt existierende compose()-Methode)
- `module_profile_sync.py` (Prompt-Modifier Seeding)
- `migrations.py` (v27)
- `Sidebar.svelte`, `App.svelte`, `api.js`

## Aufwand
| Schritt | Dateien | Aufwand |
|---------|---------|---------|
| Datenmodell + Migration | 3 | ~150 Zeilen |
| BundleComposer Service | 1 | ~200 Zeilen |
| API Router | 1 | ~200 Zeilen |
| BundleResolver Integration | 1 | ~20 Zeilen |
| Frontend View | 1 | ~400 Zeilen |
| API Client + Routing + Sidebar | 3 | ~50 Zeilen |
| i18n Strings | 14 | ~30 Zeilen |
