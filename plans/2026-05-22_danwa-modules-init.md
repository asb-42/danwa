# Handoff: danwa-modules einrichten & bestehende Module paketieren

**Datum:** 2026-05-22
**Quelle:** Danwa-Hauptprojekt `/media/data/Projekte/danwa`
**Ziel:** Neues Repository `danwa-modules` initialisieren, alle Module aus `modules/` übernehmen, validieren und paketieren

---

## Kontext aus dem Danwa-Hauptprojekt

### Modulsystem-Architektur

Danwa verwendet ein Modulsystem zur Verwaltung von Plattform-Komponenten.
Jedes Modul lebt in einem eigenen Unterverzeichnis unter `modules/{category}/{module-name}/`.
Jedes Modul besteht aus einer `manifest.json` und einer Profildatei (`profile.yaml`, `profile.json` oder `profile.md`).

### Kategorien (aus `backend/modules/type_derivation.py`)

| Verzeichnis | Modultyp (enum) |
|------------|-----------------|
| `llm-profiles/` | LLM_PROFILE |
| `agent-cores/` | AGENT_PERSONA (Prefix `agent-`) oder ROLE_TYPE (Prefix `role-`) |
| `agent-argumentation-patterns/` | PROMPT_VARIANT |
| `agent-tone-profiles/` | TONE_PROFILE |
| `agent-prompt-modifiers/` | ARGUMENTATION_PATTERN |
| `workflows/` | WORKFLOW_TEMPLATE |
| `agent-bundles/` | BUNDLE |
| `ui-translations/` | LANGUAGE_PACK |

### Vorhandene Module (aus `modules/`)

**llm-profiles/** (10 Module):
- `llm-cloud-openrouter/`, `llm-cloud-qwen/`, `llm-draft-d6f64175/`,
  `llm-local-gemma-4-26b-a4b/`, `llm-local-gemma-4-31b-it/`, `llm-local-gemma/`,
  `llm-local-glm-4-32b-0414-uncensored-heretic-v1/`, `llm-local-qwen3.5-27b-distilled/`,
  `llm-local-qwen3.6-35b-a3b/`, `llm-owl-alpha/`
- Plus: `llm-openrouter-claude-3.6-sonnet/`, `llm-openrouter-glm-5-2ond/`,
  `llm-openrouter-gpt4/`, `llm-openrouter-grok-4.20/`, `llm-openrouter-hy3-preview/`,
  `llm-owl-alpha-copy-u7rv/`, `llm-xiaomi-io-2--6btm/`, `llm-xiaomi-mimo-v2.5-pro/`
- Plus: `llm-opencodezen-minimax-m2.5-free-ry6l/`

**agent-cores/** (18 Module):
- Agent Personas: `agent-critic-default-en/`, `agent-critic-default/`,
  `agent-critic-example/`, `agent-critic-stoic/`, `agent-custom-moderator/`,
  `agent-moderator-default-en/`, `agent-moderator-default/`, `agent-moderator-example/`,
  `agent-optimizer-default-en/`, `agent-optimizer-default/`, `agent-optimizer-example/`,
  `agent-strategist-default-en/`, `agent-strategist-default/`, `agent-strategist-example/`,
  `agent-strategist-german-law/`
- Role Types: `role-analyst/`, `role-creative/`, `role-critic/`, `role-expert-reviewer/`,
  `role-external-agent/`, `role-fact-checker/`, `role-hitl-user/`, `role-moderator/`,
  `role-optimizer/`, `role-strategist/`

**agent-argumentation-patterns/** (18 Module):
- `prompt-critic/`, `prompt-critic-en/`, `prompt-dialectic-critic/`, `prompt-dialectic-critic-en/`,
  `prompt-dialectic-moderator/`, `prompt-dialectic-moderator-en/`,
  `prompt-dialectic-optimizer/`, `prompt-dialectic-optimizer-en/`,
  `prompt-dialectic-strategist/`, `prompt-dialectic-strategist-en/`,
  `prompt-kantian-critic/`, `prompt-kantian-strategist/`,
  `prompt-moderator/`, `prompt-moderator-en/`,
  `prompt-optimizer/`, `prompt-optimizer-en/`,
  `prompt-steiner-critic/`, `prompt-steiner-strategist/`,
  `prompt-strategist/`, `prompt-strategist-en/`

**agent-tone-profiles/** — leer (keine Module)

**workflows/** (8 Module):
- `workflow-socratic-debate/`, `workflow-tpl-dialectic-debate/`,
  `workflow-tpl-interview/`, `workflow-tpl-kantian-analysis/`,
  `workflow-tpl-mediation/`, `workflow-tpl-quick-review/`,
  `workflow-tpl-standard-debate/`, `workflow-tpl-streitgespraech/`

**agent-bundles/** — leer (keine Module)

**ui-translations/** — leer (keine Module)

### Manifest-Schema (v2 — Basis)

Quelldatei: `/media/data/Projekte/danwa/schemas/module-manifest.json`

```json
{
  "schema_version": "2.0.0",
  "module_id": "danwa-llm-openrouter-claude-4",
  "name": {"en": "...", "de": "..."},
  "description": {"en": "...", "de": "..."},
  "version": "1.0.0",
  "type": "llm-profile" | "agent-persona" | "role-type" | "prompt-variant" | "tone-profile" | "workflow-template" | "bundle" | "language-pack",
  "category": "llm-profiles" | "agents" | "role-types" | "prompts" | "tone-profiles" | "workflows" | "bundles" | "translations",
  "author": {"name": "...", "contact": "...", "org": "..."},
  "license": "CC-BY-4.0",
  "profile_file": "profile.yaml",
  "profile_format": "yaml" | "json" | "markdown",
  "dependencies": {"module_id": ">=1.0.0"},
  "tags": ["...", "..."],
  "language": "en" | "de" | "...",
  "checksum": "sha256...",
  "created_at": "2026-05-22T00:00:00Z",
  "updated_at": "2026-05-22T00:00:00Z"
}
```

### Typ-Ableitung aus Verzeichnisnamen

Wenn `type` oder `category` im Manifest fehlen, leitet Danwa sie ab:

**Aus dem Eltern-Verzeichnis:**
- `llm-profiles/` → LLM_PROFILE
- `agent-argumentation-patterns/` → PROMPT_VARIANT
- `workflows/` → WORKFLOW_TEMPLATE
- `agent-bundles/` → BUNDLE
- `ui-translations/` → LANGUAGE_PACK
- `agent-tone-profiles/` → TONE_PROFILE
- `agent-prompt-modifiers/` → ARGUMENTATION_PATTERN

**Aus dem `module_id`-Prefix (für gemischte Verzeichnisse wie `agent-cores/`):**
- `agent-` → AGENT_PERSONA
- `role-` → ROLE_TYPE
- `tone-` → TONE_PROFILE
- `prompt-` → PROMPT_VARIANT
- `workflow-` → WORKFLOW_TEMPLATE
- `llm-` → LLM_PROFILE
- `bundle-` → BUNDLE

### Validierungsregeln (aus `backend/modules/validation.py`)

1. `schema_version` muss `"1.0.0"` oder `"2.0.0"` sein
2. `module_id`: lowercase, alphanumeric + hyphens/dots, Pflichtfeld
3. `version` muss `^\d+\.\d+\.\d+$` entsprechen
4. `type` muss gültiger `ModuleType`-enum-Wert sein
5. `category` muss gültiger `ModuleCategory`-enum-Wert sein
6. v2-Format: `profile_file` + `profile_format` statt legacy `files[]`
7. Profildatei muss existieren, nicht leer sein
8. Checksum (SHA-256) muss stimmen
9. Keine doppelten `module_id`s im gesamten System

---

## Aufgabe: danwa-modules Repository einrichten

### Schritt 1: Repository initialisieren

1. Neues Verzeichnis `danwa-modules/` anlegen (NICHT innerhalb des Danwa-Hauptprojekts)
2. `git init`
3. README.md mit Beschreibung des Repos und der Modulstruktur anlegen
4. LICENSE (CC-BY-4.0) anlegen
5. `.gitignore` anlegen (keine system files, `.bak.*`, `.tmp_install/`)
6. `schemas/module-manifest.json` aus Danwa-Hauptprojekt kopieren und auf v3.0.0 heben:

**Schema-Änderungen für v3:**
- Neues `compatibility`-Objekt: `{danwa_min_version, danwa_max_version}`
- Neues `repository`-Objekt: `{type, url, ref}`
- `translation_stats` NICHT im Manifest – das ist dynamisch und gehört in den `index.json`

### Schritt 2: Module aus Danwa in das neue Repo übernehmen

Für jede Kategorie unter `modules/` im Danwa-Projekt:

1. Verzeichnisstruktur 1:1 übernehmen: `llm-profiles/`, `agent-cores/`, `agent-argumentation-patterns/`, `agent-tone-profiles/`, `workflows/`, `agent-bundles/`, `ui-translations/`
2. Für jedes Modul:
   a. Verzeichnis + alle Dateien kopieren
   b. `manifest.json` auf `schema_version: "3.0.0"` heben
   c. `compatibility.danwa_min_version = "2.1.0"` setzen
   d. `repository`-Feld eintragen: `{type: "github", url: "https://github.com/asb-42/danwa-modules"}`
   e. SHA-256-Checksums neu berechnen und aktualisieren
   f. Validierung durchführen (siehe Validierungsregeln oben)

### Schritt 3: GitHub Actions einrichten

#### `.github/workflows/validate.yml` — bei PR und Push auf main

```yaml
name: Validate Modules
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate all manifests
        run: |
          # Jedes manifest.json gegen schemas/module-manifest.json validieren
          # module_id-Uniqueness prüfen
          # SHA-256-Checksums prüfen
          # Profildateien auf Existenz + Format prüfen
```

#### `.github/workflows/publish.yml` — bei Git-Tag `v*`

```yaml
name: Publish Modules
on:
  push:
    tags: ["v*"]
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build index.json
        run: |
          # Alle manifests parsen, Checksums berechnen, index.json generieren
      - name: Create Release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            index.json
            releases/*.zip
          generate_release_notes: true
```

### Schritt 4: index.json-Generator

Ein Script (Python oder Node.js), das:

1. Rekursiv alle `manifest.json` unter `modules/` und Kategorie-Verzeichnissen findet
2. Jedes Manifest parst
3. SHA-256-Checksums der Profil-Dateien berechnet
4. `download_url` für GitHub Releases generiert
5. `index.json` im Root schreibt

```python
#!/usr/bin/env python3
"""Generate index.json from all module manifests."""
import json, hashlib, sys
from pathlib import Path

ROOT = Path(__file__).parent
INDEX = {"generated_at": "", "modules": []}

for manifest_path in sorted(ROOT.rglob("manifest.json")):
    manifest = json.loads(manifest_path.read_text())
    module_dir = manifest_path.parent
    
    # SHA-256 of profile file
    profile_path = module_dir / manifest.get("profile_file", "")
    checksum = hashlib.sha256(profile_path.read_bytes()).hexdigest() if profile_path.exists() else ""
    
    INDEX["modules"].append({
        "module_id": manifest["module_id"],
        "version": manifest["version"],
        "type": manifest.get("type", ""),
        "name": manifest.get("name", {}),
        "download_url": f"https://github.com/asb-42/danwa-modules/releases/download/v{manifest['version']}/{manifest['module_id']}.zip",
        "checksum_sha256": checksum,
    })

json.dump(INDEX, sys.stdout, indent=2, ensure_ascii=False)
```

### Schritt 5: Initialer Commit und Push

1. Ersten Commit: `chore: initial module repository with all Danwa modules`
2. Tag als `v1.0.0`
3. Push zu `github.com:asb-42/danwa-modules.git`

---

## Wichtige Hinweise für die Arbeit

1. **Keine UUIDs als Dateinamen** — sprechende Namen verwenden (siehe Typ-Ableitung)
2. **Jedes Modul muss valide sein** — alle Validierungsregeln aus `backend/modules/validation.py` beachten
3. **Alle 60+ Module übernehmen** — einschließlich der leeren Kategorie-Verzeichnisse für zukünftige Module
4. **CHEF-Kopie erstellen** — die Module im Danwa-Hauptprojekt bleiben unverändert, bis die Migration abgeschlossen ist
5. **`module_id` in manifest.json** ist das Primär-Identitätsfeld – das Verzeichnis ist nur Organisationshilfe
6. **Dependencies referenzieren `module_id`s**, nicht Verzeichnisnamen
7. **Alle Module haben initial Version `"1.0.0"`** — der erste Tag im neuen Repo wird `v1.0.0`

## Dateien, die aus dem Danwa-Projekt referenziert werden können

Für Validierung, Schema und Logik:
- `/media/data/Projekte/danwa/schemas/module-manifest.json`
- `/media/data/Projekte/danwa/backend/modules/validation.py`
- `/media/data/Projekte/danwa/backend/modules/models.py` (ModuleType, ModuleCategory)
- `/media/data/Projekte/danwa/backend/modules/type_derivation.py`
- `/media/data/Projekte/danwa/plans/2026-05-22_danwa-modules-roadmap.md`
