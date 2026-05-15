# ADR-002: Single Source of Truth for Application Versioning

## Status

**Accepted** — Implemented in commit 5e5a21f (initial), completed in commits 0530b43, 9fe166b.

## Date

2026-05-15

## Context

Before this decision, the application version was scattered across multiple files with no coordination:

| Ort | Wert | Status |
|-----|------|--------|
| `backend/main.py` (Docstring) | `v2.0` | Hart codiert |
| `backend/__init__.py` | `2.0.0` | Hart codiert |
| `backend/core/config.py` | `app_version: "2.0.0"` | Settings-basiert |
| `backend/a2a/agent_card.py` | `"version": "2.0.0"` | Hart codiert |
| `pyproject.toml` | `version = "2.0.0"` | PEP-621 |
| `frontend/index.html` | `Debate Engine v2.0` | HTML `<title>` |
| `frontend/package.json` | `"version": "1.1.0"` | Paket-Manager |
| `VERSION` (alt) | `0.5.0` | Verwaist |

### The Problem

1. **Kein Single Source of Truth**: Sechs verschiedene Dateien für dieselbe Nummer.
2. **Inkonsistente UI-Anzeigen**: Header, Sidebar und Health-Endpoint zeigten unterschiedliche Werte.
3. **Unklare Semantik**: `2.0.0` suggerierte einen stabilen Release, obwohl das System Pre-1.0 war.
4. **Manueller Aufwand**: Jede Versionsänderung erforderte Änderungen an 6+ Stellen.
5. **Verwaiste Dateien**: `VERSION` (0.5.0) wurde nicht mehr gelesen, aber existierte noch.

### Alternatives Considered

#### Alternative A: `pyproject.toml` als SSOT

Version nur in `pyproject.toml` definieren, alle anderen Stellen lesen daraus zur Build-Zeit.

- **Pros**: Standard-Konvention für Python-Projekte (PEP-621).
- **Cons**: Erfordert Python-Import oder Parsing zur Build-Zeit. Frontend (Svelte/Vite) kann nicht direkt auf `pyproject.toml` zugreifen. Keine einfache manuelle Änderung ohne Tooling.

#### Alternative B: Git-Tags als SSOT

Version ausschließlich aus Git-Tags ableiten (`git describe --tags`).

- **Pros**: Automatisch, keine manuelle Datei. Immer synchron mit dem Repository.
- **Cons**: Erfordert Git-Repository zur Laufzeit. Funktioniert nicht in Docker-Containern ohne `.git`. Keine Möglichkeit, Version vor dem Taggen zu setzen.

#### Alternative C: `version`-Datei als SSOT (gewählt)

Eine einzelne `version`-Datei im Projektstamm. Alle anderen Stellen lesen daraus dynamisch oder werden per Script synchronisiert.

- **Pros**: Einfach, sprachunabhängig, funktioniert überall (CI, Docker, lokal). Manuell editierbar. Keine Build-Abhängigkeiten.
- **Cons**: Erfordert Disziplin — nur diese Datei ändern. Sync-Script für `pyproject.toml`/`package.json` nötig.

## Decision

### Single Source of Truth

**Die Datei `version` (kleingeschrieben, im Projektstamm) ist die einzige Quelle der Wahrheit für die Anwendungsversion.**

```
# /version
# Format: MAJOR.MINOR.PATCH
# Dieses File ist die EINZIGE Quelle der Wahrheit.
# Nicht in config.py, __init__.py oder main.py ändern!

1.1.0
```

### Semantic Versioning

Das Projekt folgt [Semantic Versioning 2.0.0](https://semver.org/):

```
MAJOR.MINOR.PATCH

MAJOR  — Breaking Changes (API-Änderungen, DB-Migrationen, inkompatible Config)
MINOR  — Neue Features (rückwärtskompatibel)
PATCH  — Bugfixes (rückwärtskompatibel)
```

#### Empfohlene Versionshistorie

| Version | Datum | Änderung |
|---------|-------|----------|
| 0.1.0 | 2025-xx-xx | Chainlit-Vorgänger (intern) |
| 0.9.0 | 2026-xx-xx | Neustart mit FastAPI + LangGraph |
| 1.0.0 | 2026-05-15 | Modularisierung: Module-Architektur + EN-SSOT |
| 1.1.0 | 2026-05-15 | i18n (14 Sprachen), Blueprint Pipeline, Versionierung |
| 1.2.0 | künftig | Übersetzungscache + Mehrsprachigkeit-Erweiterung |
| 2.0.0 | künftig | Breaking Change (z.B. neue DB-Struktur) |

> **Empfehlung:** Der aktuelle Stand ist ein stabiles 1.x-System.
> 2.0.0 nur bei echten Breaking Changes verwenden.

### Dynamisches Ableiten

Alle Komponenten lesen die Version dynamisch aus der `version`-Datei:

#### Backend Python

**`backend/core/config.py`** — `_get_version()` liest die Datei, ignoriert Kommentarzeilen, validiert gegen `^\d+\.\d+\.\d+$`:

```python
def _get_version() -> str:
    version_file = Path(__file__).resolve().parent.parent.parent / "version"
    if not version_file.exists():
        return "0.0.0-dev"
    lines = [line.strip() for line in version_file.read_text().splitlines()
             if line.strip() and not line.strip().startswith("#")]
    if not lines:
        return "0.0.0-dev"
    ver = lines[-1].strip()
    return ver if re.match(r"^\d+\.\d+\.\d+$", ver) else "0.0.0-dev"

class Settings(BaseSettings):
    app_version: str = _get_version()
```

**`backend/__init__.py`** — `__version__` aus derselben Datei:

```python
def _get_version() -> str:
    v = Path(__file__).resolve().parent.parent / "version"
    return v.read_text().strip() if v.exists() else "0.0.0-dev"

__version__ = _get_version()
```

**`backend/a2a/agent_card.py`** — Importiert `__version__` aus `backend`:

```python
from backend import __version__
# ... "version": __version__
```

**`backend/main.py`** — FastAPI-Instanz mit `settings.app_version`:

```python
app = FastAPI(title="Danwa", version=settings.app_version)
```

#### API-Endpoints

**`GET /api/v1/config/version`** — Liefert Version, Build-Zeitstempel und Git-Commit:

```json
{
  "version": "1.1.0",
  "build": "2026-05-15T14:30:00+02:00",
  "commit": "9fe166b"
}
```

**`GET /health`** — Liefert Version aus `settings.app_version`:

```json
{ "status": "ok", "version": "1.1.0" }
```

#### Frontend

**`frontend/src/lib/api.js`** — `getVersion()` ruft `/api/v1/config/version` auf:

```js
export function getVersion() {
  return request('/api/v1/config/version');
}
```

**`frontend/src/lib/stores.js`** — `appVersion` Store:

```js
export const appVersion = writable('');
```

**`frontend/src/App.svelte`** — Lädt Version beim Start:

```js
getVersion().then((data) => { appVersion.set(data.version); });
```

**UI-Anzeigen:**
- Header (rechts oben): `v{$appVersion}`
- Sidebar (Logo): `v{$appVersion || '…'}`
- Sidebar (Footer): `{t('app.version', { version: $appVersion || '…' })}`

#### Paket-Manager-Dateien

**`pyproject.toml`** und **`frontend/package.json`** werden per Script synchronisiert:

```bash
python scripts/sync_version.py
```

Das Script liest `/version` und aktualisiert beide Dateien via Regex. Wenn die Version bereits korrekt ist, wird nichts geschrieben.

### Versionsänderung — Workflow

1. `version`-Datei editieren (z.B. `1.1.0` → `1.2.0`)
2. `python scripts/sync_version.py` ausführen (aktualisiert `pyproject.toml` + `package.json`)
3. Backend neu starten (liest Version beim Start)
4. Commit + Push

```bash
# Beispiel: Minor-Release
echo "1.2.0" > version
python scripts/sync_version.py
git add -A && git commit -m "chore: bump version to 1.2.0"
git push
```

### Build-Integration

**`scripts/stamp_version.py`** — Stempelt Build-Metadaten in `_build_info.json`:

```json
{
  "version": "1.1.0",
  "built_at": "2026-05-15T14:30:00Z"
}
```

## Consequences

### Positive

- **Single Source of Truth**: Eine Datei für die Version. Keine Widersprüche mehr.
- **Einfache Änderung**: Versionswechsel = eine Zeile editieren + Script ausführen.
- **Sprachunabhängig**: Funktioniert für Python, JavaScript, CI/CD, Docker.
- **Fallback-Sicherheit**: Wenn `version` fehlt, wird `0.0.0-dev` verwendet (kein Crash).
- **Validierung**: Regex prüft MAJOR.MINOR.PATCH-Format.
- **Git-Commit im API-Response**: Traceability von Version → Commit.

### Negative

- **Manueller Schritt**: `sync_version.py` muss nach Änderung ausgeführt werden (kann aber auch in CI automatisiert werden).
- **Zwei Dateien im Root**: `version` (SSOT) und `VERSION` (alt, wurde entfernt). Verwechslungsgefahr bei neuen Contributern.
- **PyPI-Version**: `pyproject.toml`-Version wird nur per Script aktualisiert, nicht automatisch. Wenn das Script nicht läuft, ist die PyPI-Version veraltet.

### Risiken

| Risiko | Wahrscheinlichkeit | Auswirkung | Mitigation |
|--------|-------------------|------------|------------|
| `version`-Datei gelöscht | Niedrig | Mittel | Fallback auf `0.0.0-dev`, CI-Prüfung |
| `sync_version.py` nicht ausgeführt | Mittel | Niedrig | CI-Prüfung auf Konsistenz, Pre-commit-Hook möglich |
| Falsches Format (z.B. `1.2`) | Niedrig | Niedrig | Regex-Validierung, Fallback auf `0.0.0-dev` |
| `pyproject.toml` veraltet | Mittel | Niedrig | Nur für PyPI relevant; aktuell kein PyPI-Deployment |

## References

- [Plan 017 — Versionierung](../archive/plans/2026-05-14_017-versionierung.md)
- Commit 5e5a21f: Initiale Implementierung
- Commit 0530b43: Vollständige Bereinigung hardcoded Versionen + `sync_version.py`
- Commit 9fe166b: Entfernung der verwaisten `VERSION`-Datei
- [Semantic Versioning 2.0.0](https://semver.org/)
- [ADR-001: Database as SSOT](./001-database-ssot.md)
