# Plan: danwa-modules — Modul-Repository für die Danwa-Plattform

**Datum:** 2026-05-22
**Autor:** asb

## 1. Motivation

Die Danwa-Plattform verwendet Module zur Verwaltung von LLM-Profilen, Agent Cores, Argumentation Patterns, Tone Profiles, Workflows, Bundles und UI-Übersetzungen.
Bislang liegen alle Module nur lokal unter `modules/` und sind nicht versioniert, nicht teilbar und nicht über externe Quellen installierbar.

Ziel ist ein separates GitHub-Repository `danwa-modules`, das:

- Module versioniert und paketiert bereitstellt
- Teilen und Wiederverwenden von Modulen ermöglicht
- Direkte Installation aus dem Repo via Danwa-UI erlaubt
- Validierung und Qualitätssicherung via CI/CD durchsetzt
- Automatische Synchronisation von UI-Übersetzungen zwischen Danwa und dem Modul-Repo ermöglicht

## 2. Repository-Struktur

```
danwa-modules/
├── llm-profiles/
│   └── llm-openrouter-claude-4/
│       ├── manifest.json
│       └── profile.yaml
├── agent-cores/
│   ├── agent-critic-default-en/
│   │   ├── manifest.json
│   │   └── profile.yaml
│   ├── agent-strategist-default/
│   └── role-critic/
├── agent-argumentation-patterns/
│   ├── prompt-critic/
│   └── prompt-strategist-en/
├── agent-tone-profiles/
├── agent-prompt-modifiers/
├── workflows/
│   ├── workflow-tpl-standard-debate/
│   └── workflow-tpl-dialectic-debate/
├── agent-bundles/
├── ui-translations/
│   └── danwa-translations-de/
├── schemas/
│   ├── module-manifest.json
│   └── migration-guide.md
├── index.json                         # automatisch generiert, compiled catalog
├── .github/
│   └── workflows/
│       ├── publish.yml                # bei Tag/Release → index.json + ZIPs bauen
│       └── validate.yml               # PR-Check: alle manifests gegen Schema
├── .gitignore
├── LICENSE
└── README.md
```

**Jede Modul-Kategorie bekommt ein eigenes Unterverzeichnis** (wie im aktuellen Danwa-Projekt).
Die `type_derivation.py` in Danwa kann weiterhin aus dem Verzeichnisnamen den Modultyp ableiten.

## 3. Dateinamen: Sprechende Namen (keine UUIDs)

Aktuell wird `parent_dir_name()` in `type_derivation.py` genutzt, um Typ und Kategorie aus dem Verzeichnisnamen abzuleiten.
Sprechende Verzeichnisnamen sind essenziell für:

- `git diff` und Code-Review
- Debugging und Fehlersuche
- Navigation im Repository

UUIDs wären im Quell-Repo kontraproduktiv. Die UUID-Idee lebt in installierten Kopien unter `data/modules/` im Danwa-Projekt, nicht hier.

## 4. Schema-Erweiterung: Version 3.0.0

Das aktuelle Schema (`schemas/module-manifest.json`) kennt keine Kompatibilitätsangaben, keine Repository-Quellen und keine Übersetzungsstatistiken.

### Neue Felder im Manifest (v3):

```json
{
  "schema_version": "3.0.0",
  "module_id": "danwa-translations-de",
  "name": {"en": "German Translation Pack", "de": "Deutsches Übersetzungspaket"},
  "version": "1.2.0",
  "type": "language-pack",
  "locale": "de",
  "source_locale": "en",
  "compatibility": {
    "danwa_min_version": "2.1.0",
    "danwa_max_version": null
  },
  "repository": {
    "type": "github",
    "url": "https://github.com/asb-42/danwa-modules",
    "ref": "v1.2.0"
  },
  "dependencies": {
    "danwa-llm-openrouter": ">=2.0.0"
  }
}
```

### index.json (autogeneriert, nicht im Manifest):

Dynamische Metriken wie `translation_stats` gehören in den **autogenerierten `index.json`**, nicht in die statische `manifest.json`:

```json
{
  "generated_at": "2026-05-22T12:00:00Z",
  "danwa_version": "2.1.0",
  "modules": [
    {
      "module_id": "danwa-translations-de",
      "version": "1.2.0",
      "type": "language-pack",
      "locale": "de",
      "translation_stats": {
        "total_strings": 939,
        "translated": 894,
        "untranslated": 45,
        "coverage_pct": 95.2,
        "last_synced": "2026-05-22T10:00:00Z",
        "outdated": 12
      },
      "download_url": "https://github.com/asb-42/danwa-modules/releases/download/v1.2.0/danwa-translations-de.zip",
      "checksum_sha256": "abc123..."
    }
  ]
}
```

**Der `index.json` wird per GitHub Action bei jedem Tag/Release neu gebaut.**
Das erlaubt Danwa, schnell alle verfügbaren Module + aktuelle Versionen + Stats abzurufen,
ohne das gesamte Repo zu klonen.

## 5. GitHub Actions CI/CD

### validate.yml — bei jedem PR und Push auf main

| Schritt | Beschreibung |
|---------|-------------|
| `check-manifests` | Jedes `manifest.json` gegen `schemas/module-manifest.json` validieren |
| `check-module-ids` | `module_id` muss eindeutig sein (keine Duplikate im gesamten Repo) |
| `check-checksums` | SHA-256 der referenzierten Files prüfen |
| `check-dependencies` | Referenzierte Dependencies existieren im gleichen Repo |
| `check-duplicate-files` | Keine Datei in zwei Modulen (außer Symlinks) |

### publish.yml — bei Git-Tag `v*`

| Schritt | Beschreibung |
|---------|-------------|
| `build-zips` | Pro Modul ein ZIP-Archiv bauen (nur die Dateien aus `files[]`) |
| `build-category-zips` | Optional: ein ZIP pro Kategorie für Bulk-Install |
| `generate-index` | `index.json` aus allen Manifests + Checksummen + Stats generieren |
| `create-release` | GitHub Release anlegen mit allen ZIPs + `index.json` |

## 6. Danwa-Backend: Neue API-Endpunkte

### `POST /api/v1/modules/install-from-repo`

```json
{
  "source": "github",
  "repo": "asb-42/danwa-modules",
  "module_id": "danwa-translations-de",
  "version": "1.2.0"
}
```

Ablauf:
1. `index.json` aus dem Repo laden (`raw.githubusercontent.com`)
2. Checksumme validieren
3. ZIP aus den GitHub Releases herunterladen
4. Existierenden `install_from_url()`-Pfad nutzen
5. Dependencies prüfen (siehe Punkt 7)

### `GET /api/v1/modules/repo-index?repo=asb-42/danwa-modules`

- Holt `index.json` (mit 5-Minuten-Caching)
- Listet alle verfügbaren Module mit Version + Stats

### `POST /api/v1/modules/check-repo-updates`

- Vergleicht lokale installierte Versionen mit Repo-Index
- Gibt Liste von Modulen mit verfügbaren Updates zurück

## 7. Dependency Resolution

Aktuell werden `dependencies` im `module_registry` gespeichert, aber nie ausgewertet.

**Neu:** Beim Installieren wird geprüft:

1. Alle referenzierten Dependencies sind installiert
2. Die installierten Versionen erfüllen die semver-Constraints (`>=1.0.0`, `^2.0.0`, etc.)
3. Keine zirkulären Dependencies
4. Bei Fehler: klare Meldung mit Liste der fehlenden Module

Dafür muss Danwa eine semver-Bibliothek einführen (`packaging` oder `semver`).
Aktuell wird nur `!=` verglichen — das reicht nicht.

## 8. Danwa-Frontend: ModuleManager.svelte erweitern

Der bestehende `ModuleManager.svelte` bekommt einen neuen Tab "GitHub":

```
┌────────────────────────────────────────────────┐
│ Build → Modules                                 │
│ ┌─────────┬──────────┬──────────────┐          │
│ │ Lokal   │ GitHub   │ Updates (3)  │          │
│ └─────────┴──────────┴──────────────┘          │
│                                                 │
│ GitHub-Module durchsuchen... [🔍]               │
│                                                 │
│ ┌─────────────────────────────────────────┐     │
│ │ 🌐 danwa-translations-de       v1.2.0   │     │
│ │ German Translation Pack                  │     │
│ │ 894/939 übersetzt (95%)     [Install]  │     │
│ ├─────────────────────────────────────────┤     │
│ │ 🤖 agent-critic-default-en   v2.1.0     │     │
│ │ English Critic Agent (Default)          │     │
│ │ aktuelle Version installiert  [✓]     │     │
│ ├─────────────────────────────────────────┤     │
│ │ 🧠 llm-openrouter-claude-4    v0.9.0   │     │
│ │ Neu!                          [Install] │     │
│ └─────────────────────────────────────────┘     │
└─────────────────────────────────────────────────┘
```

Der "Updates"-Tab listet nur Module, bei denen `remote_version > local_version`.

## 9. i18n-Sync-Automatismus

UI-Strings leben in `frontend/src/lib/i18n/loaders/`. Wenn sich dort etwas ändert
(neue Strings, gelöschte Strings, geänderte Keys), soll ein automatischer Prozess
einen PR im `danwa-modules`-Repo aufmachen:

1. Danwa-CI extrahiert alle UI-Strings + zählt `total_strings`
2. Generiert ein aktualisiertes Translation-Base-Modul (`danwa-translations-base`)
3. Öffnet PR in `danwa-modules`: `chore: update translation base (942 strings)`
4. Ändert `translation_stats` für alle Sprachpakete:
   - `total_strings` wird aktualisiert
   - `translated` bleibt gleich
   - `untranslated` steigt entsprechend
   - `coverage_pct` sinkt
   - `outdated` markiert geänderte Keys

**Offene Frage:** Soll der Sync Push oder Pull sein?
- **Push:** Danwa-CI pushed direkt ins Modul-Repo (braucht Repo-Zugriff)
- **Pull:** Cron-Job im Modul-Repo pollt Danwa-Releases (braucht kein Cross-Repo-Token)

Empfehlung: **Push** — die Danwa-CI hat ohnehin Zugriff auf beide Repos.

## 10. Sicherheit

| Maßnahme | Beschreibung |
|----------|-------------|
| **Checksum-Verifikation** | SHA-256 jeder Datei und des ZIPs wird vor Installation geprüft (existiert bereits) |
| **Signatur (optional)** | GPG-Signatur im `manifest.json` für vertrauenswürdige Module |
| **Quell-Validierung** | Module werden nur aus konfigurierten Repos akzeptiert (Whitelist) |
| **Sandboxing** | Module enthalten nur Konfiguration (YAML/JSON/Markdown), keinen ausführbaren Code |
| **Dependency-Lock** | `index.json` fixiert Checksummen – kein Man-in-the-Middle bei ZIP-Download |

## 11. Offene Punkte / Nächste Schritte

| # | Punkt | Entscheidung nötig |
|---|-------|-------------------|
| 1 | **Monorepo vs. Kategorie-Repos** | Ein Repo für alle Module vs. eins pro Kategorie? Empfehlung: **Monorepo** (einfacher zu verwalten, Querverweise möglich) |
| 2 | **Release-Strategie** | Ein Tag pro Modul (`v1.2.0`) oder ein Gesamt-Release? Empfehlung: **pro Modul** (unabhängige Versionierung) |
| 3 | **Übersetzungs-Sync-Richtung** | Push (Danwa → Modul-Repo) oder Pull (Modul-Repo → Danwa)? Siehe Punkt 9 |
| 4 | **Premium/Private Module** | Soll es später auch private Repos geben? Dann braucht es einen API-Key-Mechanismus |
| 5 | **Moderations-Prozess** | Wer reviewed PRs im Modul-Repo? Nur der Repo-Owner oder Community? |
| 6 | **Versionierung der bestehenden Module** | Alle Module in `modules/` haben `"1.0.0"`. Soll es ein initialer `v1.0.0`-Tag für alle sein? |

## 12. Migration der bestehenden Module

Alle 60+ Module aus `modules/` müssen ins `danwa-modules`-Repo übertragen werden.
Dabei:

1. **Manifest-Check:** Jedes `manifest.json` gegen `schema_version: "3.0.0"` prüfen
2. **`compatibility`-Feld:** Für alle Module `danwa_min_version: "2.1.0"` setzen
3. **`repository`-Feld:** Für alle Module das neue Repo eintragen
4. **Checksums-Neuberechnung:** Nach Kopie neue SHA-256-Checksums erstellen
5. **Entfernen der `modules/` aus Danwa-Repo (optional):** Langfristig sollen Module nur noch aus dem Modul-Repo installiert werden
6. **Bootstrapping:** Danwa muss seine eigenen Module beim ersten Start aus dem Modul-Repo installieren können

## Anhänge

### A. Bestehende Infrastruktur in Danwa (wird genutzt, nicht ersetzt)

| Komponente | Datei | Zweck |
|-----------|-------|-------|
| `ModuleInstaller` | `backend/modules/installer.py` | Installations-Logik (ZIP, Directory) |
| `ModuleService` | `backend/modules/service.py` | Service-Layer für Modul-Management |
| `ModuleValidator` | `backend/modules/validation.py` | Manifest-Validierung & Checksum-Prüfung |
| `ModuleType` | `backend/modules/models.py` | 11 Modultypen |
| `ModuleCategory` | `backend/modules/models.py` | 9 Kategorien |
| `type_derivation.py` | `backend/modules/type_derivation.py` | Typ + Kategorie aus Verzeichnis ableiten |
| `module-manifest.json` | `schemas/module-manifest.json` | JSON-Schema für Manifeste |
| `ModuleManager.svelte` | `frontend/src/components/ModuleManager.svelte` | Modul-UI (Build → Modules) |
| `modules.py` | `backend/api/routers/modules.py` | REST-API für Module |
| `api.js` | `frontend/src/lib/api.js` | Frontend-API-Client für Module |

### B. Fehlende Komponenten (müssen entwickelt werden)

| Komponente | Beschreibung |
|-----------|-------------|
| **semver-Resolver** | Korrekte semver-Constraint-Prüfung (`>=1.0.0`, `^2.0.0`) |
| **Dependency-Resolver** | Prüfung und Auflösung von Modul-Abhängigkeiten |
| **GitHub-Index-Reader** | Abruf und Caching von `index.json` aus GitHub |
| **GitHub-Release-Downloader** | Download von ZIPs aus GitHub Releases |
| **UI-Tab "GitHub"** | Anzeige verfügbarer Module im `ModuleManager.svelte` |
| **Update-Checker** | Vergleich lokaler vs. remote Versionen mit semver |
| **i18n-Sync-GHA** | GitHub Action für Translation-Base-Sync |
