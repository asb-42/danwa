# Todo-Liste: Plan 20 — Mehrsprachigkeit & Lokalisierung

> **Referenz:** [Plan 20](../plans/020-i18n-mehrsprachigkeit.md)  
> **Datum:** 2026-05-15  
> **Gesamtaufwand:** Geschätzt 5-8 Sprints  

---

## Phase 1: Backend-Infrastruktur

- [x] **1.1** `data/translations.db` SQLite-Schema definieren
  - Datei: `backend/services/translation_service.py`
  - Tabelle: `translations` (id, key, locale, value, source, confidence, reviewed_by, version, timestamps)
  - Indizes: `(locale, key)`, `(locale)`
  
- [x] **1.2** `TranslationService` Klasse implementieren
  - CRUD: `set_translation()`, `get_translation()`, `get_translations_bulk()`, `delete_translation()`
  - Fallback-Kette: Primärsprache → EN → Key
  - `get_all_keys()`, `get_stats()`, `resolve_with_fallback()`
  
- [x] **1.3** REST-API: `GET /api/v1/i18n/locales`
  - Liste der 12 Standardsprachen + optionale RTL-Sprachen
  - Antwort: `{ default, locales: [...], locale_names: {...} }`

- [x] **1.4** REST-API: `GET /api/v1/i18n/{locale}`
  - Alle Übersetzungen für eine Sprache zurückgeben
  - Query-Param `keys` für seitenweises Laden

- [x] **1.5** REST-API: `GET /api/v1/i18n/{locale}/{key}`
  - Einzelne Übersetzung abrufen

- [x] **1.6** REST-API: `POST /api/v1/i18n/{locale}`
  - Übersetzung erstellen oder aktualisieren
  - Body: `{ key, value, source }`

- [x] **1.7** REST-API: `POST /api/v1/i18n/translate`
  - LLM-Ad-hoc-Übersetzung
  - Body: `{ text, source_locale, target_locale, llm_profile_id? }`

- [x] **1.8** REST-API: `POST /api/v1/i18n/bulk-translate`
  - Batch-Übersetzung für initiale Lokalisierung
  - Body: `{ keys: string[], source_locale, target_locale }`

- [x] **1.9** REST-API: `DELETE /api/v1/i18n/{locale}/{key}`
  - Übersetzung löschen (nur `source=manual`)

- [x] **1.10** LLM-Auswahllogik: `_select_llm_for_locale()`
  - Sprachspezifische LLM-Zuordnung (z.B. DeepSeek für CJK, Gemini für Hindi)

- [x] **1.11** Tests: TranslationService (Unit)

---

## Phase 2: Frontend-Architektur

- [x] **2.1** i18n Store erweitern (`frontend/src/lib/i18n/index.js`)
  - HTTP-Loading via `fetch('/api/v1/i18n/{locale}')`
  - Lokaler Cache (`Map<string, Map<string, string>>`)
  - Drei-Level-Fallback: locale → en → key
  - `getAvailableLocales()` API-Call
  - `isRTL(locale)` Helper

- [x] **2.2** `LanguageSwitcher.svelte` erweitern
  - Dropdown mit Flaggen-Icons + Spaltennamen
  - Such-Feld für schnelles Finden
  - Anzeige: "Deutsch (de)", "English (en)", "中文 (zh)" etc.

- [x] **2.3** API-Client erweitern (`frontend/src/lib/api.js`)
  - `getSupportedLocales()`, `getTranslations()`, `setTranslation()`
  - `translateViaLLM()`, `bulkTranslate()`

- [x] **2.4** RTL-Layout-Support
  - Dynamisches `dir`-Attribut auf `<html>` setzen
  - CSS Logical Properties statt physischer Properties
  - Icons spiegeln (← →)

- [x] **2.5** Per-Projekt-Spracheinstellung
  - `project.settings.default_locale` Feld hinzufügen
  - Language-Selector in ProjectSettings-Komponente

- [x] **2.6** Debatte-Sprache als Metadaten
  - `debate.language` Feld bereits vorhanden → nutzen
  - Language-Badge in DebateView/ArchiveView

---

## Phase 3: Standard-Sprachdateien generieren

- [x] **3.1** Englische Basis-Datei (`en.js`) als Quelle definieren
  - Alle Keys bereits vorhanden (~830+ Einträge)

- [ ] **3.2** LLM-Batch-Generierung: Deutsch (de.js)
  - Status: ✅ bereits vorhanden & gepflegt

- [ ] **3.3** LLM-Batch-Generierung: Französisch (fr.js)
  - Prompt: "Übersetze alle UI-Strings ins Französische"
  - Spezial: Formelle Anrede (vous) konsistent verwenden

- [ ] **3.4** LLM-Batch-Generierung: Spanisch (es.js)

- [ ] **3.5** LLM-Batch-Generierung: Italienisch (it.js)

- [ ] **3.6** LLM-Batch-Generierung: Portugiesisch (pt.js)
  - Hinweis: BR-PT vs. EU-PT → BR als Standard

- [ ] **3.7** LLM-Batch-Generierung: Russisch (ru.js)
  - Hinweis: Pluralregeln beachten (one/few/many)

- [ ] **3.8** LLM-Batch-Generierung: Chinesisch (zh.js)
  - Hinweis: CJK-Zeichen, vereinfacht als Standard

- [ ] **3.9** LLM-Batch-Generierung: Japanisch (ja.js)
  - Hinweis: Keigo-Stufe wählen (Standard: polite form)

- [ ] **3.10** LLM-Batch-Generierung: Koreanisch (ko.js)

- [ ] **3.11** LLM-Batch-Generierung: Schwedisch (sv.js)

- [ ] **3.12** LLM-Batch-Generierung: Griechisch (el.js)

- [ ] **3.13** Manuelles Review jeder Sprachdatei
  - Checkliste: Pluralformen, Formatierung, Kontext

---

## Phase 4: RTL-Sprachunterstützung (Optional)

- [ ] **4.1** Arabisch (ar.js) generieren
- [ ] **4.2** Hebräisch (he.js) generieren
- [ ] **4.3** CSS Logical Properties Audit durchführen
- [ ] **4.4** RTL-spezifische Layout-Bugs fixen
- [ ] **4.5** Bidirektionaler Text (BiDi) in Debatte-Transkripten testen

---

## Phase 5: Tests & Qualitätssicherung

- [ ] **5.1** Unit-Tests für TranslationService (`tests/test_translation_service.py`)
  - CRUD-Operationen, Fallback-Logik, LLM-Integration
  
- [ ] **5.2** API-Tests für i18n-Endpoints (`tests/backend/test_i18n_api.py`)
  - GET locales, GET translations, POST/DELETE
  
- [ ] **5.3** Playwright E2E-Tests: Sprachwechsel in der UI
  - DE → EN → FR → ZH → zurück
  
- [ ] **5.4** Visual Regression Tests
  - Alle 12 Sprachen: Screenshots der Hauptseiten
  
- [ ] **5.5** Coverage-Report generieren
  - Welche Keys fehlen pro Sprache?

---

## Phase 6: Deployment & Dokumentation

- [ ] **6.1** `/docs/technical_documentation.md` aktualisieren (i18n-Abschnitt)
- [ ] **6.2** `/docs/user_manual.md` aktualisieren (Sprachwechsel-Anleitung)
- [ ] **6.3** `README.md` Localization-Abschnitt erweitern
- [ ] **6.4** Setup-Skript aktualisieren (Standard-Sprachpakete)
- [ ] **6.5** Git-Commit: "Plan 20: i18n Multi-Language Support"

---

## Wichtige Hinweise

### Fortsetzungspunkte nach Crash/Unterbrechung
- Prüfe die Todo-Liste oben → erstes nicht-erledigtes Item = Fortsetzungspunkt
- Git-Branch: `i18n-multilang` (noch zu erstellen)

### Glossar
- **Locale**: Sprachcode (z.B. `de`, `zh`, `ar`)
- **Source**: Herkunft der Übersetzung (`manual`, `llm_generated`, `auto_generated`)
- **Fallback-Kette**: locale → en → key (letzter Ausweg)
- **RTL**: Right-to-Left (Arabisch, Hebräisch)
