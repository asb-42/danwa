# Sprint 2 — Modulformat + Import-Engine

> **Branch:** `feature/module-architecture`  
> **Dauer:** 1 Woche  
> **Liefergegenstand:** Modul-Installer, Validator, erste Module als Dateien

---

## Kontext

Sprint 1 hat die Grundlagen (Manifest-Schema, DB-Tabellen, EN-SSOT) gelegt. Jetzt wird die Import-Logik implementiert und die bestehenden Dateien in das neue Modulformat überführt.

---

## Todo-Liste

### 2.1 — ModuleValidator implementieren

- [ ] Klasse `ModuleValidator` in `backend/modules/validation.py`
  - [ ] `validate_manifest(manifest: dict) → list[str]` — Fehlerliste
  - [ ] Schema-Version prüfen (aktuell: `1.0.0`)
  - [ ] `module_id`-Format prüfen: `danwa-{category}-{name}-v{major}` oder frei
  - [ ] `checksum` gegen Dateien verifizieren
  - [ ] `dependencies` auflösen und Kompatibilität prüfen
  - [ ] Konflikte mit bereits installierten Modulen erkennen
  - [ ] Datei-Integrität: keine leeren Dateien, keine doppelten Pfade
- [ ] `validate_prompt_file(path: str) → list[str]`:
  - [ ] Mindestens 50 Zeichen Content
  - [ ] Keine offensichtlichen Platzhalter (TODO, FIXME, ersetzen)
  - [ ] Rollen-Bezeichner in Dateiname vs. `role_type_id` in Manifest abgleichen
- [ ] `validate_workflow_json(data: dict) → list[str]`:
  - [ ] Pflichtfelder: `name`, `nodes[]`, `edges[]`
  - [ ] Knoten-Referenzen in Edges müssen existieren
  - [ ] Kein zirkulärer Graph (Topologie-Check)
- [ ] `verify_checksums(base_dir: Path, manifest: dict) → bool`

### 2.2 — ModuleInstaller implementieren

- [ ] Klasse `ModuleInstaller` in `backend/modules/installer.py`
  - [ ] `install_from_directory(path: str) → InstallationReport`:
    - [ ] Manifest lesen
    - [ ] Validierung durchführen
    - [ ] Checksums verifizieren
    - [ ] Dateien nach `modules/{module_id}/` kopieren
    - [ ] In `module_registry` eintragen
    - [ ] EN-Inhalte in `module_translation_cache` importieren
    - [ ] DE-Übersetzungen aus bestehenden DE-Dateien importieren (falls vorhanden)
    - [ ] `InstallationReport` zurückgeben (Status, Anzahl Dateien, Warnungen)
  - [ ] `install_from_url(url: str) → InstallationReport`:
    - [ ] ZIP herunterladen
    - [ ] Entpacken in Temp-Verzeichnis
    - [ ] `install_from_directory()` aufrufen
  - [ ] `uninstall(module_id: str) → UninstallationReport`:
    - [ ] Dateien entfernen
    - [ ] DB-Einträge löschen (oder als `enabled=false` markieren)
    - [ ] Abhängigkeits-Check: kein anderes installiertes Modul davon abhängig?
  - [ ] `update(module_id: str) → ModuleInfo`:
    - [ ] Neue Version vergleichen
    - [ ] In-Place-Update oder Seite-an-Seite-Installation
    - [ ] Übersetzungscache invalidieren bei geänderten Dateien
  - [ ] `rollback(module_id: str, version: str)`:
    - [ ] Vorherige Version aus Backup-Verzeichnis wiederherstellen

### 2.3 — ModuleService (Haupt-Service)

- [ ] Klasse `ModuleService` in `backend/modules/service.py`
  - [ ] `discover_local() → list[ModuleInfo]`: Installierte Module scannen
  - [ ] `discover_remote(registry_url: str) → list[ModuleManifest]`:
    - [ ] `GET {registry_url}/registry.json` laden
    - [ ] Manifeste parsen und zurückgeben
    - [ ] Für Remote-Discovery: `https://raw.githubusercontent.com/danwa/modules/main/registry.json`
  - [ ] `get(module_id: str) → ModuleInfo | None`
  - [ ] `list_all(category: str | None = None) → list[ModuleInfo]`
  - [ ] `install(module_id: str, source: ModuleSource) → InstallationReport`
  - [ ] `uninstall(module_id: str) → UninstallationReport`
  - [ ] `update(module_id: str) → ModuleInfo`
  - [ ] `translate(module_id: str, target_lang: str, force: bool = False) → TranslationResult`:
    - [ ] Hash-Abgleich: Ist Übersetzung noch aktuell?
    - [ ] Wenn nicht → LLM-Übersetzung generieren
    - [ ] Cache-Eintrag erstellen/bearbeiten
    - [ ] Quality-Score berechnen (String-Ähnlichkeit mit Back-Translation)

### 2.4 — API-Endpunkte für Module

- [ ] Neuer Router `backend/api/routers/modules.py`:
  - [ ] `GET /api/v1/modules/` — Liste installierter Module mit Status
  - [ ] `GET /api/v1/modules/available` — Verfügbare Remote-Module
  - [ ] `GET /api/v1/modules/{module_id}` — Details
  - [ ] `POST /api/v1/modules/install` — Install (body: `{module_id, source_url?}`)
  - [ ] `POST /api/v1/modules/{module_id}/uninstall` — Deinstallieren
  - [ ] `PUT /api/v1/modules/{module_id}/update` — Aktualisieren
  - [ ] `GET /api/v1/modules/{id}/translations` — Übersetzungstatus
  - [ ] `POST /api/v1/modules/{id}/translate` — Übersetzung auslösen
  - [ ] `POST /api/v1/modules/validate` — Validierung ohne Installation

### 2.5 — Bestehende Dateien in Modulstruktur migrieren

- [ ] Skript `scripts/migrate_profiles.py`:
  - [ ] Liest `profiles/agents/*.yaml` → erzeugt `modules/danwa-agents-base/`
  - [ ] Liest `profiles/llm/*.yaml` → erzeugt `modules/danwa-llm-profiles/`
  - [ ] Liest `profiles/prompts/default/*.md` → erzeugt `modules/danwa-prompts-base/prompts/default/`
  - [ ] Liest `profiles/argumentation-patterns/*/*.md` → erzeugt `modules/danwa-prompts-base/prompts/argumentation-patterns/`
  - [ ] Liest `profiles/workflow-variants/*/*.md` → erzeugt `modules/danma-workflow-variants/`
  - [ ] Liest `templates/*.json` → erzeugt `modules/danwa-workflow-templates/`
  - [ ] Erzeugt für jedes Modul ein `manifest.json` mit korrekten Checksums
  - [ ] Kopiert DE-Dateien nach `.export-temp/` (für späteren Import ins `danwa-modules` Repo)

### 2.6 — Kategorien für Modulverwaltung

Folgende Kategorien werden im UI angezeigt:

| Kategorie | Module | Icon |
|-----------|--------|------|
| **Prompts & Patterns** | `danwa-prompts-base`, Pattern-Module | 📝 |
| **Agenten-Personas** | `danwa-agents-base` | 👤 |
| **LLM-Konfigurationen** | `danwa-llm-profiles` | ⚙️ |
| **Workflow-Templates** | `danwa-workflow-templates` | 🔄 |
| **Workflow-Varianten** | `danma-workflow-variants` | 🎛️ |
| **Übersetzungen** | Übersetzungsmodule pro Sprache | 🌐 |

### 2.7 — Tests

- [ ] `tests/backend/test_module_validator.py`:
  - [ ] Valid Manifest akzeptieren
  - [ ] Fehlendes `module_id` ablehnen
  - [ ] Falsche Checksum ablehnen
  - [ ] Fehlende Abhängigkeit ablehnen
  - [ ] Kollision mit bestehendem Modul ablehnen
- [ ] `tests/backend/test_module_installer.py`:
  - [ ] Installation aus Verzeichnis
  - [ ] Installation idempotent
  - [ ] Deinstallation entfernt Dateien + DB-Einträge
  - [ ] Update von v1.0.0 → v1.1.0
  - [ ] Rollback auf v1.0.0
- [ ] `tests/backend/test_module_service.py`:
  - [ ] Lokale Discovery
  - [ ] Remote Discovery (Mock)
  - [ ] Kategorisierung
- [ ] Bestehende Tests (`test_workflow_nodes.py`, `test_debate_api.py` etc.) müssen weiterhin bestehen

---

## Abhängigkeiten
- Benötigt Sprint 1 (Manifest-Schema, DB-Tabellen)
- Unabhängig von Übersetzungslogik (Sprint 3)

## Akzeptanzkriterien
- [ ] AC-2.1: Modulvalidierung erkennt fehlerhafte Manifeste
- [ ] AC-2.2: Installation kopiert Dateien und schreibt DB
- [ ] AC-2.3: Deinstallation entfernt alles sauber
- [ ] AC-2.4: Remote-Discovery funktioniert (lokal getestet)
- [ ] AC-2.5: Alle bisherigen Dateien sind als Module migriert
- [ ] AC-2.6: API-Endpunkte sind dokumentiert und erreichbar
- [ ] AC-2.7: 50+ neue Modultests, alle bestehenden Tests weiterhin grün
