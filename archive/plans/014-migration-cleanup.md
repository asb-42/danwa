# Sprint 5 — Migration & Aufräumen

> **Branch:** `feature/module-architecture`  
> **Dauer:** 1 Woche  
> **Liefergegenstand:** Vollständige Migration, Cleanup, Abwärtskompatibilität

---

## Kontext

Die Module-Struktur steht. Jetzt werden **alle** alten Dateien migriert, die Abwärtskompatibilitätsschicht aktiviert und die alten Pfade deprecated.

---

## Todo-Liste

### 5.1 — Prompts-Migration

- [ ] `scripts/migrate_prompts.py`:
  - [ ] Liest `profiles/prompts/default/*.md` (EN + DE)
  - [ ] Schreibt EN-Dateien nach `modules/danwa-prompts-base/prompts/default/`
  - [ ] Erzeugt `manifest.json` für `danwa-prompts-base`
  - [ ] Importiert in DB (EN als Original, DE als Übersetzungscache)
  - [ ] Erzeugt Checksum-Datei `.checksums.json`
  - [x] DEPRECATED-Datei in `profiles/prompts/default/` ablegen

### 5.2 — Argumentation Patterns Migration

- [ ] `scripts/migrate_argumentation_patterns.py`:
  - [ ] Liest `profiles/argumentation-patterns/*/*.md`
  - [ ] Verschiebt nach `modules/danwa-prompts-base/prompts/argumentation-patterns/`
  - [ ] Entfernt `profiles/prompts/variants/` (nach Migration)
  - [ ] Workflow-Prompts (`profiles/prompts/variants/dialectic/`) → `modules/danwa-workflow-templates/workflows/dialectic/`
  - [ ] DEPRECATED-Dateien in alten Verzeichnissen
- [ ] Alte `profiles/prompts/README.md` aktualisieren mit Verweis auf neue Struktur

### 5.3 — Agent-Personas Migration

- [ ] `scripts/migrate_agents.py`:
  - [ ] Liest `profiles/agents/*.yaml`
  - [ ] Migriert nach `modules/danwa-agents-base/agents/`
  - [ ] Erzeugt `manifest.json` mit Abhängigkeit auf `danwa-prompts-base`
  - [ ] Importiert YAML-Inhalte in DB (als `agent-persona`-Module)
  - [ ] Validierung: Keine doppelten IDs

### 5.4 — LLM-Profile Migration

- [ ] `scripts/migrate_llm_profiles.py`:
  - [ ] Liest `profiles/llm/*.yaml`
  - [ ] Migriert nach `modules/danwa-llm-profiles/llm/`
  - [ ] **Achtung:** API-Keys sind NICHT in den YAMLs → nur Verweise auf `.env`-Variablen
  - [ ] `.env.example` mit Platzhaltern erzeugen
  - [ ] `manifest.json` für LLM-Profile
- [ ] `profiles/llm/` → DEPRECATED-Marker

### 5.5 — Workflow-Templates Migration

- [ ] `scripts/migrate_templates.py`:
  - [ ] Liest `templates/*.json`
  - [ ] Migriert nach `modules/danwa-workflow-templates/workflows/`
  - [ ] Erzeugt `manifest.json`
- [ ] Bestehende `dialectic_debate.json` → in `workflows/dialectic/` (Workflow-Prompts kommen mit)

### 5.6 — Workflow-Varianten Migration

- [ ] `scripts/migrate_variants.py`:
  - [ ] Liest `profiles/workflow-variants/*/*.md`
  - [ ] Migriert nach `modules/danma-workflow-variants/variants/`
  - [ ] Erzeugt `manifest.json`

### 5.7 — Abwärtskompatibilitätsschicht

- [ ] **Dateisystem-Fallback:** Alte `profiles/`-Dateien weiterhin lesbar (mit Deprecation-Warning in Logs)
- [ ] `PromptsService.get_prompt()` Logik:
  ```python
  1. Prüfe module_translation_cache (DB)
  2. Prüfe modules/ (neues Dateisystem)
  3. Prüfe profiles/ (altes Dateisystem, mit Warning)
  4. Fehler, wenn nichts gefunden
  ```
- [ ] `from_legacy()` / `to_legacy()`-Funktionen für Roundtrip-Kompatibilität
- [ ] `DeprecationWarning` bei jedem Zugriff auf alte Pfade
- [ ] Konfigurations-Flag: `ENABLE_LEGACY_PATHS = True` (Standard: True für Übergangszeit)

### 5.8 — Cleanup-Skript

- [ ] `scripts/cleanup_legacy.py`:
  - [ ] Listet alle veralteten Dateien auf
  - [ ] Zeigt an, ob sie noch von Alt-Code-Pfaden referenziert werden
  - [ ] Option: `--remove` entfernt alte Dateien (nach Abschluss von Phase 2)
  - [ ] Sicherheitswarnung: "Sind Sie sicher?"

### 5.9 — Tests

- [ ] `tests/backend/test_migration.py`:
  - [ ] Alle Prompts migriert und konsistent
  - [ ] Alle Agent-Personas migriert
  - [ ] Alle LLM-Profile migriert
  - [ ] Alle Templates migriert
  - [ ] Abwärtskompatibilität: alter Zugriff gibt korrekte Prompts zurück
  - [ ] Hash-Verifizierung nach Migration
- [ ] Bestehende Tests müssen alle weiterhin bestehen
- [ ] Regressionstest: Modul-Import + Prompt-Abruf + Übersetzung in einem Flow

---

## Abhängigkeiten
- Benötigt Sprint 1–3 vollständig

## Akzeptanzkriterien
- [ ] AC-5.1: Alle Prompts in Modulstruktur, keine Prompts mehr in `profiles/`
- [ ] AC-5.2: Alle Agent-Personas in Module migriert
- [ ] AC-5.3: Alle LLM-Profile in Module migriert (ohne API-Keys)
- [ ] AC-5.4: Abwärtskompatibilität funktioniert (Legacy-Pfad gibt gleiche Ergebnisse)
- [ ] AC-5.5: 100% Testabdeckung der Migrationsskripte
- [ ] AC-5.6: Kein Datenverlust nach Migration (Hash-Vergleich)
