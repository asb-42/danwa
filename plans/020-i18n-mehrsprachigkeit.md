# Plan 20: Konsequente Mehrsprachigkeit & Lokalisierung

> **Datum:** 2026-05-15  
> **Status:** Planung / Todo-Liste  
> **Priorität:** Medium  

---

## 1. Übersicht

Danwa unterstützt derzeit 2 Sprachen (Deutsch, Englisch) über statische JS-Dictionary-Dateien.  
Dieser Plan beschreibt die Architektur für **12 Standardsprachen** + optional **2 RTL-Sprachen** (Arabisch, Hebräisch).

### 1.1 Standard-Sprachen (12)

| Code | Sprache     | Besonderheiten                         |
|------|-------------|----------------------------------------|
| de   | Deutsch     | Basis-Sprache, Default-Locale          |
| en   | Englisch    | Basis-Sprache, Fallback                |
| fr   | Französisch | Formelle/Informelle Anrede (tu/vous)   |
| es   | Spanisch    | T-Vornamen üblich                      |
| it   | Italienisch | T-Vornamen üblich                      |
| pt   | Portugiesisch| BR vs. PT Varianten möglich           |
| ru   | Russisch    | Kyrillisch, komplexe Pluralregeln      |
| zh   | Chinesisch  | CJK-Zeichen, vereinfacht/traditionell  |
| ja   | Japanisch   | CJK, Keigo (formelle Sprache)          |
| ko   | Koreanisch  | Hangul, Höflichkeitsstufen             |
| sv   | Schwedisch  | Bokmål-nahe                           |
| el   | Griechisch  | 3 Genera, komplexe Deklination         |

### 1.2 Optionale RTL-Sprachen (2)

| Code | Sprache     | Besonderheiten                              |
|------|-------------|---------------------------------------------|
| ar   | Arabisch    | RTL, komplexe Morphologie, Dialekte          |
| he   | Hebräisch   | RTL, einzigartige Pluralregeln               |

---

## 2. Architektur-Entwurf

### 2.1 Drei-Schichten-Architektur

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND (Svelte 5)               │
│                                                     │
│  ┌──────────────┐  ┌───────────────┐  ┌───────────┐ │
│  │ i18n Core    │→ │  Locale Cache  │→ │  HTTP API │ │
│  │ (Store)      │  │  (Map<String>) │  │  Client   │ │
│  └──────────────┘  └───────────────┘  └───────────┘ │
│       │                │                  │           │
│       │         ┌──────┴──────┐    ┌──────┴──────┐  │
│       │         │ Local Dict  │    │  Backend     │  │
│       │         │ (bundled)   │    │  /api/v1/i18n│  │
│       │         └─────────────┘    └───────────┬──┘  │
│       │                                        │     │
└─────────────────────────────────────────────────────┘
                                          │
                                  ┌───────▼────────┐
                                  │   BACKEND       │
                                  │                 │
                                  │ ┌────────────┐  │
                                  │ │ SQLite DB   │  │
                                  │ │ translations │  │
                                  │ └────────────┘  │
                                  │ ┌────────────┐  │
                                  │ │ LLM Service │  │
                                  │ │ (Ad-hoc)    │  │
                                  │ └────────────┘  │
                                  │ ┌────────────┐  │
                                  │ │ REST API    │  │
                                  │ └────────────┘  │
                                  └─────────────────┘
```

### 2.2 Schicht 1: Frontend i18n Core

- **Svelte Store** mit reaktiven Wörterbüchern
- **Drei Fallback-Ebenen:** Primärsprache → EN → Key
- **Pluggable Formatter:** Zahlen, Datum, Währung, Plural gemäß `Intl`
- **RTL-Layout-Support** via CSS `dir="rtl"` toggle
- **Lazy Loading** von Sprachpaketen

### 2.3 Schicht 2: Backend Translation Service

- **SQLite für persistente Übersetzungen** (pro Projekt)
- **CRUD-API** für manuelle Übersetzungen
- **LLM-Ad-hoc-Übersetzung** für unbekannte Keys
- **Versionierung & Audit-Trail** (wer hat wann was übersetzt?)
- **Auto-Generierung** der 12 Standard-Sprachdateien aus den DE/EN-Basics

### 2.4 Schicht 3: LLM-Ad-hoc-Engine

- Nutzt den im Projekt konfigurierten LLM-Provider
- Kontext-bewusste Übersetzung (UI-Strings vs. Debatte-Inhalte)
- Batch-Verarbeitung für initiale Lokalisierung
- Qualitätssicherung durch Confidence-Scoring

---

## 3. Detaildesign

### 3.1 Datenmodell (Backend)

```sql
CREATE TABLE translations (
    id              TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    key             TEXT NOT NULL,
    locale          TEXT NOT NULL,
    value           TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'manual',
    -- 'manual' | 'llm_generated' | 'llm_reviewed' | 'auto_generated'
    confidence      REAL,  -- LLM confidence score (0.0-1.0)
    reviewed_by     TEXT,  -- user ID who reviewed
    version         INTEGER DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(key, locale)
);

CREATE INDEX idx_translations_locale ON translations(locale);
CREATE INDEX idx_translations_key ON translations(key);
```

### 3.2 REST-API-Spezifikation

| Methode | Pfad                         | Beschreibung                           |
|---------|------------------------------|----------------------------------------|
| GET     | `/api/v1/i18n/locales`       | Liste unterstützter Sprachen           |
| GET     | `/api/v1/i18n/{locale}`      | Alle Übersetzungen einer Sprache       |
| GET     | `/api/v1/i18n/{locale}/meta` | Meta-Info (Coverage %, letzte Änderung)|
| GET     | `/api/v1/i18n/{locale}/{key}`| Einzelne Übersetzung                   |
| POST    | `/api/v1/i18n/{locale}`      | Übersetzung erstellen/bearbeiten        |
| POST    | `/api/v1/i18n/translate`     | LLM-Ad-hoc-Übersetzung                 |
| POST    | `/api/v1/i18n/bulk-translate`| Batch LLM-Übersetzung                  |
| DELETE  | `/api/v1/i18n/{locale}/{key}`| Übersetzung löschen                    |

### 3.3 Frontend-API-Client

```javascript
// Neue Funktionen in api.js
export function getSupportedLocales()
export function getTranslations(locale, keys = null)
export function getTranslation(locale, key)
export function setTranslation(locale, key, value)
export function deleteTranslation(locale, key)
export function translateViaLLM(text, sourceLocale, targetLocale)
export function bulkTranslate(keys, sourceLocale, targetLocale)
```

### 3.4 Svelte i18n Store (Erweiterung)

```javascript
// Erweiterte Struktur
const i18n = {
    // ... bestehende Funktionalität
    loadLocale(locale)           // HTTP-Fetch + lokaler Cache
    getTranslationsForPage(keys) // Seitenweise Laden
    getAvailableLocales()        // API-Call
    isRTL(locale)                // RTL-Erkennung
    setDirection(locale)         // dir=rtl/ltr setzen
    pluralize(count, key)        // Erweitert mit locale-aware rules
    formatNumber/date/currency   // Intl-basiert
};
```

### 3.5 RTL-Unterstützung (CSS-Architektur)

```css
/* CSS-Logik für RTL */
[dir="rtl"] .debate-card {
    /* Automatische Spiegelung via CSS logical properties */
    border-inline-start: 3px solid var(--accent);
    /* margin-inline-start statt margin-left */
}

/* Logical Properties statt physischer */
/* ❌ margin-left → ✅ margin-inline-start */
/* ❌ padding-right → ✅ padding-inline-end */
/* ❌ text-align: left → ✅ text-align: start */
```

### 3.6 Pluralregeln pro Sprache

| Sprache | Plural-Regel (Intl.PluralRules)          |
|---------|-------------------------------------------|
| de      | one (1), other                            |
| en      | one (1), other                            |
| ru      | one (1, 21, 31...), few (2-4, 22-24...), many (0, 5-20...), other |
| zh      | other (alle)                              |
| ja      | other (alle)                              |
| ko      | one (1), other                            |
| fr      | one (0, 1), other (pascal: 0 → many)     |
| el      | one (1), other                            |
| sv      | one (1), other                            |

---

## 4. Umsetzungsphasen

### Phase 1: Backend-Infrastruktur (P1)
1. SQLite-Tabelle `translations` erstellen
2. TranslationService implementieren (CRUD)
3. REST-API-Endpunkte aufsetzen
4. LLM-Ad-hoc-Übersetzungsfunktion
5. Batch-Translation-Endpoint

### Phase 2: Frontend-Architektur (P2)
1. i18n Store erweitern (HTTP-Loading, Cache, Fallback)
2. LanguageSwitcher-Komponente erweitern
3. RTL-Detection und Layout-Support
4. `dir`-Attribut dynamisch setzen

### Phase 3: Standard-Sprachdateien (P3)
1. Automatisierte Generierung der 12 Sprachen via LLM-Batch
2. Manuelle Review-Workflows für kritische Strings
3. Coverage-Reporting pro Sprache

### Phase 4: UI-Integration (P4)
1. Language-Selector in Sidebar/Config
2. Per-Projekt-Spracheinstellung
3. Debatte-Sprache als Meta-Daten
4. RTL-Sprachunterstützung (optional)

### Phase 5: Testing & Qualitätssicherung (P5)
1. Unit-Tests für TranslationService
2. API-Tests für i18n-Endpoints
3. Playwright-Tests für UI-Sprachwechseln
4. Visual Regression Tests für RTL-Layout

---

## 5. RTL-Überlegungen (Optional)

### 5.1 CSS-Vorbereitung
- Alle Layouts auf **CSS Logical Properties** umstellen
- `margin-inline-start` statt `margin-left`
- `padding-inline-end` statt `padding-right`
- `border-start-start-radius` statt `border-top-left-radius`
- `text-align: start` statt `text-align: left`

### 5.2 Svelte-Komponenten
- `dir`-Attribut auf `<html>` oder Root-Container setzen
- Icons, die eine Richtung haben (← →), müssen gespiegelt werden
- Bidi-Algorithmus für gemischte LTR/RTL-Inhalte beachten

### 5.3 Spezifische RTL-Bedürfnisse
- Arabische Schrift: `arabic-forms` (initial, medial, final, isolated)
- Farsi-Zahlen vs. arabische Zahlen
- Hebräisch: Vokalzeichen optional
- Numerische Systeme: Hindi-Ziffern in Arabisch

---

## 6. Nicht-funktionale Anforderungen

| Anforderung          | Detail                                                        |
|----------------------|---------------------------------------------------------------|
| Performance          | Lazy-Loading; Sprachpakete < 50KB (gzipped)                  |
| SEO                  | `hreflang` Tags für jede Sprache                             |
| Accessibility        | `lang`-Attribut korrekt setzen; Screenreader-Kompatibilität  |
| Offline-First        | Übersetzungen im Browser-Cache (localStorage/IndexedDB)      |
| Pluggable           | Neue Sprachen ohne Code-Änderung hinzufügbar                 |
| Audit               | Alle Übersetzungsänderungen nachvollziehbar                   |
