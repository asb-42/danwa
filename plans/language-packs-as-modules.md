# Language Packs als Module — Plan

## Analyse: Kollisionsrisiko

**Ergebnis: Keine Kollisionen.** Die beiden Translation-Systeme sind vollständig isoliert:

| Aspekt | Modul-Übersetzungen | UI i18n |
|--------|---------------------|---------|
| Datenbank | `data/blueprints.db` | `data/i18n/ui_translations.db` |
| Tabelle | `module_translation_cache` | `ui_translations` |
| Service | `TranslationService` | `UITranslationService` |
| API | `/api/v1/translation/` | `/api/v1/i18n/` |
| SSOT | Dateisystem (`modules/*/profile.md`) | Bundled JS (`en.js`) |

Modul-Inhalte (Prompts, Personas) und UI-Strings überschneiden sich **nicht**. Ein Language-Pack-Modul kann beides enthalten, aber die Installer-Logik muß beide Pfade separat bedienen.

## SSOT-Prinzip

| System | SSOT | Language Pack Rolle |
|--------|------|---------------------|
| Module | EN-Dateien im Dateisystem | Language Packs sind **abgeleitete Übersetzungen** (Suffix `-de`, `-es`), referenzieren das EN-Original |
| UI i18n | `en.js` (bundled) | Language Packs sind **Custom-Varianten** mit eigenem Namespace, kollidieren nicht mit bundled Loadern |

**Namenskonvention:** `lang-{locale}-{name}` z.B. `lang-de-custom`, `lang-es-mine`
- Das Locale-Suffix (`-de`) kennzeichnet die Zielsprache
- Der Name-Teil (`-custom`) unterscheidet mehrere Packs für dieselbe Sprache
- Module-ID enthält immer Bindestrich (Validierung existiert bereits)

## Architektur-Übersicht

```
Language Pack ZIP
├── manifest.json          ← ModuleManifest (type=language-pack, category=translations)
├── ui_strings.json        ← UI i18n: { "nav.dashboard": "Dashboard", ... }
└── module_translations/   ← Optional: übersetzte Modul-Inhalte
    ├── profile.de.md      ← Prompt-Übersetzung
    └── persona.de.json    ← Persona-Übersetzung

Installationsfluss:
1. ZIP entpacken → manifest.json validieren
2. ui_strings.json → ui_translations.db (namespace = "langpack:{module_id}")
3. module_translations/* → module_translation_cache (existing flow)
4. module_registry Eintrag erstellen

Deinstallation:
1. ui_translations WHERE namespace = "langpack:{module_id}" DELETE
2. module_translation_cache WHERE module_id = {module_id} DELETE (CASCADE)
3. module_registry DELETE
4. Dateien entfernen
```

## Implementierungs-Phasen

### Phase 1: Backend — Models & Enums

**Datei:** `backend/modules/models.py`

- `ModuleType.LANGUAGE_PACK = "language-pack"` hinzufügen
- `ModuleCategory.TRANSLATIONS = "translations"` hinzufügen
- `LanguagePackData` Pydantic-Modell:
  ```python
  class LanguagePackData(BaseModel):
      locale: str                    # "de", "es", "fr"
      source_locale: str = "en"      # Basissprache
      key_count: int = 0             # Anzahl Keys
      coverage: float = 0.0          # Vollständigkeit vs. en.js
      ui_strings_file: str = "ui_strings.json"
      module_translations: list[str] = []  # Pfade zu übersetzten Modul-Dateien
  ```

### Phase 2: Backend — Installer-Erweiterung

**Datei:** `backend/modules/installer.py`

- `_register_in_db()` erweitern: Bei `type=language-pack`:
  - `ui_strings.json` parsen
  - Einträge in `ui_translations.db` schreiben mit `namespace = "langpack:{module_id}"`
  - `source = "bundle_imported"`
- `_uninstall()` erweitern:
  - UI-Strings mit matching namespace löschen
- `_export_module()` erweitern:
  - `ui_strings.json` aus `ui_translations.db` generieren
  - In ZIP packen mit Manifest

### Phase 3: Backend — Migration

**Datei:** `backend/blueprints/migrations.py`

- Keine neue Migration nötig — `ui_translations.db` hat bereits `namespace` Spalte
- `module_registry.category` akzeptiert bereits beliebige Strings

### Phase 4: Backend — API-Endpoints

**Datei:** `backend/api/routers/modules.py`

- Bestehende Endpoints funktionieren bereits für neue Type/Category
- Optional: `POST /api/v1/i18n/{locale}/export` — erzeugt ZIP aus DB-Inhalten
  - Exportiert alle UI-Strings einer Locale als `ui_strings.json` + Manifest
  - `Content-Disposition: attachment; filename=lang-{locale}-custom.zip`

**Datei:** `backend/api/routers/ui_i18n.py`

- `GET /api/v1/i18n/{locale}/export` — ZIP-Export für Language Pack

### Phase 5: Frontend — ModuleManager Erweiterung

**Datei:** `frontend/src/components/ModuleManager.svelte`

- Kategorie-Reihenfolge erweitern: `[..., 'translations']` ans Ende
- Neue Kategorie "Translations" mit eigenem Icon (🌐)
- Formular für Language Packs:
  - Locale (Dropdown: de, fr, es, it, pt, ru, zh, ja, ko, sv, el, ar, he + custom)
  - Source Locale (default: en)
  - Key Count (read-only, nach Import)
  - Coverage % (read-only, vs. en.js)
- Actions: Import ZIP, Export ZIP, Delete
- Edit-Modal: Nur Metadaten (Name, Beschreibung), Strings sind read-only

### Phase 6: Frontend — i18n Loader dynamisch

**Datei:** `frontend/src/lib/i18n/index.js`

- Beim App-Start: installierte Language-Packs via API abfragen
- Dynamisch als zusätzliche Locale registrieren (z.B. `de-custom`)
- Fallback-Kette: `de-custom → de → en → key`
- Bundled Loader bleibt SSOT für Basis-Locales

### Phase 7: Export-Funktion (Translation Dashboard → Language Pack)

**Datei:** `backend/api/routers/ui_i18n.py`

- `POST /api/v1/i18n/{locale}/export-as-pack`
- Body: `{ name: "Custom German", description: "..." }`
- Generiert:
  1. `manifest.json` mit `type=language-pack`, `module_id=lang-{locale}-custom`
  2. `ui_strings.json` aus DB
  3. ZIP-Archiv als Download

## Dateischema: Language Pack ZIP

```
lang-de-custom.zip
├── manifest.json
│   {
│     "schema_version": "2.0.0",
│     "module_id": "lang-de-custom",
│     "name": {"en": "German (Custom)", "de": "Deutsch (Custom)"},
│     "description": {"en": "Custom German translation"},
│     "version": "1.0.0",
│     "type": "language-pack",
│     "category": "translations",
│     "language": "de",
│     "author": {"name": "User"},
│     "license": "CC-BY-4.0",
│     "profile_file": "ui_strings.json",
│     "profile_format": "json"
│   }
└── ui_strings.json
    {
      "nav.dashboard": "Dashboard",
      "debate.title": "Debatte",
      ...
    }
```

## Risikobewertung

| Bereich | Risiko | Begründung |
|---------|--------|------------|
| Datenbank | **NIEDRIG** | Separate DBs, namespace-Isolation |
| Modul-Installer | **MITTEL** | Neue Logik für UI-Strings, aber isoliert von bestehender Logik |
| i18n Loader | **MITTEL** | Dynamisches Laden erfordert Store-Änderung |
| Namenskonflikte | **NIEDRIG** | Module-ID-Validierung + namespace-Prefix |
| SSOT | **NIEDRIG** | Language Packs sind explizit abgeleitete Varianten |
| Uninstall | **NIEDRIG** | Namespace-basierte Cleanup-Logik |

## Abgrenzung: Was Language Packs NICHT sind

- **Keine** Übersetzung von Modul-Inhalten (Prompts, Personas) — das bleibt beim bestehenden `TranslationService`
- **Kein** Ersatz für bundled Loader — `en.js`, `de.js` etc. bleiben SSOT für Basis-Sprachen
- **Keine** automatische Synchronisation — Custom-Sprachen sind Snapshots, keine Live-Views

## Offene Fragen

1. **Sollen Language Packs auch Modul-Inhalts-Übersetzungen enthalten können?**
   - Empfehlung: Ja, optional. `module_translations/` Verzeichnis im ZIP.
   - Installer erkennt beide Formate und verteilt auf die richtigen DBs.

2. **Coverage-Berechnung für Custom-Sprachen?**
   - `key_count / total_keys_in_en_js * 100`
   - Anzeige im ModuleManager als Fortschrittsbalken.

3. **Konflikt wenn zwei Language Packs dieselbe Locale bedienen?**
   - Namespace-Isolation verhindert Datenkollision.
   - UI: User wählt aktives Language Pack pro Locale.
   - Fallback: bundled Loader → aktives Pack → en.js.
