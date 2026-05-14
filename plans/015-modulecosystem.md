# Sprint 6 — Modulecosystem: GitHub-Repo, Export & Community

> **Branch:** `feature/module-architecture`  
> **Dauer:** 1 Woche  
> **Liefergegenstand:** Externes Repository, Export/Import, Dokumentation

---

## Kontext

Alle Module sind im Projekt unter `modules/` verfügbar. Jetzt wird das externe GitHub-Repo `danwa-modules` erstellt, der Export-Mechanismus gebaut und die Community-Dokumentation geschrieben.

---

## Todo-Liste

### 6.1 — GitHub-Repository einrichten

- [ ] Repository `danwa-modules` auf GitHub anlegen (oder org)
  - [ ] Public oder Private (empfohlen: Public für Community, Tags für Releases)
- [ ] `modules/.export-temp/` → Inhaltstruktur als Vorlage
- [ ] CI/CD-Pipeline einrichten:
  - [ ] Automatische Tests bei PR (Modulvalidierung)
  - [ ] Automatische Release-Erstellung bei Tag
  - [ ] `registry.json` bei jedem Release aktualisieren
- [ ] Branch-Schutzregeln: `main` nur über PRs, Reviews erforderlich

### 6.2 — Export-Mechanismus

- [ ] Skript `scripts/export_to_repo.py`:
  - [ ] Liest alle Module aus `modules/`
  - [ ] Erzeugt für jedes Modul ein ZIP (oder Git-Subdirectory)
  - [ ] Erzeugt/aktualisiert `registry.json`:
    ```json
    {
      "schema_version": "1.0.0",
      "generated_at": "2026-05-13T00:00:00Z",
      "modules": [
        {
          "module_id": "danwa-prompts-base",
          "version": "1.0.0",
          "download_url": "https://github.com/danwa/modules/releases/download/v1.0.0/danwa-prompts-base.zip",
          "checksum": "sha256:abc...",
          "type": "argumentation-pattern",
          "category": "prompts"
        }
      ]
    }
    ```
  - [ ] Commit + Push in `danwa-modules` Repo
  - [ ] GitHub Release erstellen mit ZIP-Artefakten
- [ ] `scripts/import_from_repo.py`:
  - [ ] Liest `registry.json` von Remote
  - [ ] Zeigt verfügbare Module an
  - [ ] Download + Validierung + Installation

### 6.3 — Remote Discovery Integration

- [ ] ModuleService.discover_remote() implementieren:
  - [ ] URL konfigurierbar (Default: `https://raw.githubusercontent.com/danwa/modules/main/registry.json`)
  - [ ] Timeout + Fehlerbehandlung
  - [ ] Caching: Registry nicht bei jedem Start laden (Cache: 24h)
  - [ ] Proxy-Support für Unternehmensnetzwerke

### 6.4 — Deinstallation und Update-Workflow

- [ ] `ModuleService.uninstall()`:
  - [ ] Entfernt Dateien aus `modules/{module_id}/`
  - [ ] Löscht DB-Einträge aus `module_registry` + `module_translation_cache`
  - [ ] Prüft Abhängigkeiten: Fehlschlag, wenn anderes Modul davon abhängt
  - [ ] Erzeugt Backup in `modules/.deleted/{module_id}-{timestamp}/`
- [ ] `ModuleService.update()`:
  - [ ] Prüft Remote auf neue Version (via `registry.json`)
  - [ ] Download + Validierung + Seite-an-Seite-Installation
  - [ ] Alte Version bleibt als Rollback erhalten
  - [ ] Übersetzungscache wird invalidiert und bei Bedarf neu übersetzt

### 6.5 — Sicherheitsüberlegungen

- [ ] Modul-Sandboxing:
  - [ ] Module können **nur** Prompts, YAML und JSON enthalten
  - [ ] **Keine** ausführbaren Dateien (.py, .sh, .js)
  - [ ] **Keine** Binary-Dateien
  - [ ] Validierung prüft Dateitypen-Whitelist
- [ ] Checksum-Verifizierung bei jedem Modul
- [ ] Abhängigkeitsgraphen: Keine zirkulären Abhängigkeiten
- [ ] Signierte Module (optional, langfristig): GPG-Signatur der Manifeste

### 6.6 — Dokumentation

- [ ] `docs/001-module-development-guide.md`:
  - [ ] Wie erstelle ich ein Modul?
  - [ ] Manifest-Schema-Referenz
  - [ ] Best Practices für Prompts
  - [ ] Checkliste vor Veröffentlichung
- [ ] `docs/002-module-administration.md`:
  - [ ] Wie installiere ich Module?
  - [ ] Wie aktualisiere ich Module?
  - [ ] Wie deinstalliere ich Module?
  - [ ] Wie erstelle ich eigene Übersetzungen?
- [ ] CHANGELOG-Eintrag für diese Änderung
- [ ] ADR für Modul-Architektur finalisieren (ADR-0042 aktualisieren)

### 6.7 — Beispiel-Module für Community

- [ ] `danwa-example-custom-persona`:
  - [ ] Zeigt, wie man eine eigene Agenten-Persona erstellt
  - [ ] Minimal: 1 YAML + 1 Manifest
- [ ] `danwa-example-custom-pattern`:
  - [ ] Zeigt, wie man ein Argumentationsmuster erstellt
  - [ ] Minimal: 7 Prompt-Dateien + 1 Manifest
- [ ] `danwa-example-custom-workflow`:
  - [ ] Zeigt, wie man einen Workflow erstellt
  - [ ] Minimal: Template-JSON + Manifest

### 6.8 — Tests

- [ ] `tests/backend/test_module_lifecycle.py`:
  - [ ] Kompletter Zyklus: Install → List → Update → Uninstall → Reinstall
  - [ ] Abhängigkeitsmanagement-Tests
  - [ ] Parallel-Installation mehrerer Module
- [ ] E2E-Tests:
  - [ ] Modul über UI installieren
  - [ ] Modul über UI deinstallieren
  - [ ] Remote-Module anzeigen lassen
  - [ ] Update-Check
- [ ] Sicherheitstest: Versuch, schädliche Dateien zu importieren (werden abgelehnt)

---

## Abhängigkeiten
- Benötigt Sprint 1–5 vollständig

## Akzeptanzkriterien
- [ ] AC-6.1: `danwa-modules` Repo existiert mit CI/CD
- [ ] AC-6.2: Export-Skript erzeugt korrekte `registry.json` + ZIPs
- [ ] AC-6.3: Import über Remote-URL funktioniert
- [ ] AC-6.4: Deinstallation entfernt alles sauber (inkl. Backup)
- [ ] AC-6.5: Module können keine ausführbaren Dateien enthalten
- [ ] AC-6.6: Dokumentation vollständig und veröffentlicht
- [ ] AC-6.7: Drei Beispiel-Module erstellt
- [ ] AC-6.8: 40+ neue Tests, alle bestehenden Tests weiterhin grün
