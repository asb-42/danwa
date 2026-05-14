# Sprint 1 — EN-SSOT + Übersetzungscache: Grundlagen

> **Branch:** `feature/module-architecture`  
> **Dauer:** 1 Woche  
> **Liefergegenstand:** Manifest-Schema, DB-Modelle, Migrations-Skript, EN-Bereinigung

---

## Kontext

- Englisch (EN) wird als **einzige Quelldatei-Sprache** (SSOT) festgelegt
- Alle DE-Dateien werden als initiale Übersetzungscache-Einträge in die DB importiert
- Neue Sprachen (ZH, …) werden künftig per LLM-Übersetzung + Cache generiert
- **Korrekturerkenntnis:** LLM-Profile enthalten **keine** API-Keys, sondern Verweise auf `.env`-Dateien → können portiert werden

---

## Todo-Liste

### 1.1 — Manifest-Schema definieren

- [x] **Manifest-Schema** (`schemas/module-manifest.json`) als JSON-Schema definieren
- [x] Felder: `schema_version`, `module_id`, `name`, `description`, `version`, `type`, `category`, `author`, `license`, `dependencies`, `tags`, `language`, `checksum`, `files[]`
- [x] `type`-Enum: `argumentation-pattern`, `agent-persona`, `llm-profile`, `workflow-template`, `tone-profile`, `workflow-variant`, `bundle`
- [x] Jedes `file`-Objekt hat: `path`, `role_type_id` (optional), `format`, `checksum`, `language`
- [ ] **Review:** Schema mit Nutzungsfällen gegenprüfen

### 1.2 — Modul-Datenmodell in PostgreSQL

- [ ] **Tabelle `module_registry`** erstellen:
  ```
  module_id          VARCHAR(128)  PK
  name               JSONB        (en, de, …)
  description        TEXT
  type               VARCHAR(32)
  category           VARCHAR(64)
  version            VARCHAR(16)
  author             JSONB
  license            VARCHAR(32)
  checksum           VARCHAR(64)   (SHA-256)
  installed_at       TIMESTAMPTZ
  updated_at         TIMESTAMPTZ
  enabled            BOOLEAN       DEFAULT true
  source_url         VARCHAR(512)  NULL
  source_schema      VARCHAR(16)
  ```
- [ ] **Tabelle `module_translation_cache`** erstellen:
  ```
  id                 UUID          PK
  module_id          VARCHAR(128)  FK → module_registry
  file_path          VARCHAR(256)
  language           VARCHAR(5)    (de, en, zh, …)
  translated_content TEXT
  source_hash        VARCHAR(64)
  quality_score      FLOAT         DEFAULT 0.0
  generated_at       TIMESTAMPTZ
  generated_by       VARCHAR(128)  (llm_profile_id)
  approved           BOOLEAN       DEFAULT false
  ```
- [ ] **Migration** als idempotentes SQL-Skript oder Alembic-Migration

### 1.3 — Verzeichnisstruktur für Module anlegen

- [ ] Neues Verzeichnis `modules/` im Projektstamm
- [x] Unterverzeichnisse anlegen:
  ```
  modules/
  ├── .gitignore              (module-*.zip, *.tmp)
  ├── .export-temp/           (← temporär, für späteren Export ins danwa-modules Repo)
  ├── danwa-prompts-base/
  │   ├── manifest.json
  │   └── prompts/
  │       └── default/
  │           └── (EN-Quelldateien)
  ├── danwa-agents-base/
  │   ├── manifest.json
  │   └── agents/
  ├── danwa-llm-profiles/
  │   ├── manifest.json
  │   └── llm/
  ├── danwa-workflow-templates/
  │   ├── manifest.json
  │   └── workflows/
  ├── danma-workflow-variants/
  │   ├── manifest.json
  │   └── variants/
  └── README.md
  ```
- [ ] `.gitignore` für `modules/.export-temp/` und `*.zip`

### 1.4 — EN-Bereinigung der Prompts

- [ ] **Regel:** Nur EN-Dateien sind Quelldateien. DE-Dateien werden zu Übersetzungscache-Einträgen.
- [ ] `profiles/prompts/default/strategist.md` → EN-Quelldatei behalten
- [ ] `profiles/prompts/default/strategist-en.md` → DE-Datei wird Übersetzungscache (nicht mehr Datei)
- [ ] Für jede Prompt-Datei: Hash berechnen, in `manifest.json` eintragen
- [ ] **Konsistenz-Check:** Alle EN-Quelldateien müssen vollständig sein — keine Lücken bei Rollen × Patterns

### 1.5 — Deploy-Import-Skript (Rohversion)

- [ ] Skript `scripts/deploy-import.py`:
  - [ ] Liest `modules/*/manifest.json`
  - [ ] Berechnet SHA-256 pro Datei und vergleich mit Manifest
  - [ ] Importiert EN-Inhalte in `module_registry` + `module_translation_cache` (language=en)
  - [ ] Erzeugt für DE-Dateien initiale Cache-Einträge (als `approved=true` für mitgelieferte Übersetzungen)
  - [ ] Setzt `source_file` auf relativen Pfad für Nachvollziehbarkeit
- [x] Skript ist idempotent (Hash-Abgleich → nur Änderungen importieren)

### 1.6 — PromptService anpassen

- [ ] `PromptsService.get_prompt()` umstellen:
  - [ ] Zuerst in `module_translation_cache` nach `module_id + file_path + language` suchen
  - [ ] Cache-Treffer → zurückgeben
  - [ ] Cache-Miss → EN-Quelldatei laden (Datei als Fallback) → übersetzen → cachen → zurückgeben
  - [ ] Fallback-Kette: DB-Cache → EN-Datei → Fehler
- [ ] `PromptsService.assemble_prompt()` nutzt jetzt die neue Pipeline

### 1.7 — Tests

- [ ] Neue Testdatei `tests/backend/test_module_registry.py`:
  - [ ] Modulmanifest validieren
  - [ ] Modul in DB importieren
  - [ ] Übersetzungscache lesen/schreiben
  - [ ] Hash-Vergleich bei Aktualisierung
  - [ ] Abwärtskompatibilität: alter PromptService-Zugriff gibt weiterhin korrekte Prompts zurück
- [ ] Alle bestehenden Prompts-Tests müssen weiterhin bestehen
- [ ] Testabdeckung: ≥ 90% für neue Module

---

## Abhängigkeiten

- Keine — kann parallel zu laufender Arbeit beginnen
- Benötigt Ergebnis von Sprint 2 für vollständigen Import, aber Grundlagen reichen für Sprint 2

## Akzeptanzkriterien

- [ ] AC-1.1: `manifest.json`-Schema validiert korrekt
- [ ] AC-1.2: `module_registry`- und `module_translation_cache`-Tabellen existieren
- [ ] AC-1.3: EN-Dateien sind einzige Quelldateien für Prompts
- [ ] AC-1.4: Deploy-Import-Skript läuft fehlerfrei
- [ ] AC-1.5: PromptService liest aus DB-Cache (nicht aus Dateien zur Runtime)
- [ ] AC-1.6: Alle bestehenden Prompts-Tests bestehen
- [ ] AC-1.7: DE-Sprache wird über Übersetzungscache bedient

---

## Risiko

| Risiko | Impact | Mitigation |
|--------|--------|-----------|
| Hash-Berechnung inkonsistent | Hoch | Tests mit bekannten Fixwerten |
| DE-Übersetzung geht verloren | Hoch | Vor Import sichern, automatisierte Verifizierung |
| Bestehender Code bricht ab | Mittel | Fallback auf Datei-System beibehalten bis Sprint 5 |
