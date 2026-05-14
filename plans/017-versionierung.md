# Punkt 2 — Versionierung: Konzept & Umsetzung

> **Branch:** `feature/module-architecture`
> **Dauer:** 1–2 Tage (kleiner Sprint oder Teilaufgabe)
> **Liefergegenstand:** Einheitliches Versionsschema, Quellen der Wahrheit, Workflow-Integration

---

## 1. Ist-Zustand — das aktuelle Chaos

| Ort | Version | Status |
|-----|---------|--------|
| `backend/main.py` (Docstring) | `v2.0` | Hart codiert |
| `backend/__init__.py` | `2.0.0` | Hart codiert |
| `backend/core/config.py` | `app_version: "2.0.0"` | Settings-basiert |
| `backend/a2a/agent_card.py` | `"version": "2.0.0"` | Hart codiert |
| `pyproject.toml` | `version = "2.0.0"` | PEP-621 |
| `frontend/package.json` | Abhängig von pyproject? | Unklar |
| `frontend/src/lib/i18n/loaders/*` | Keine Versionsreferenz | — |
| UI-Anzeige | "Danwa v2.0", "Debate-Agent v2.0" | Inkonsistent |

**Probleme:**
- Kein single source of truth
- Niemand weiß, wann die Version zuletzt geändert wurde oder warum
- UI zeigt unterschiedliche Strings an
- `backend/__init__.py` vs. `config.py` vs. `pyproject.toml` — drei verschiedene Stellen für dieselbe Nummer

---

## 2. Vorschlag: Semantic Versioning mit Single Source of Truth

### 2.1 Versionierungs-Schema

```
MAJOR.MINOR.PATCH

Beispiele:
  1.0.0   — Erster offizieller Release (falls gewünscht)
  1.1.0   — Neues Feature (z.B. Modularisierung, neue Gesprächsformen)
  1.1.1   — Bugfix
  2.0.0   — Breaking Change (z.B. neue Datenbankstruktur, API-Änderungen)
```

### 2.2 Single Source of Truth: `VERSION`-Datei

**Eine einzige Datei** im Projektstamm:

```
# /version
# Format: MAJOR.MINOR.PATCH
# Dieses File ist die EINZIGE Quelle der Wahrheit.
# Nicht in config.py, __init__.py oder main.py ändern!

1.1.0
```

### 2.3 Automatische Ableitung in alle anderen Stellen

**`pyproject.toml`:**
```toml
[tool.uv]
# Version wird aus /version gelesen (via Script oder uv build)
version = "1.1.0"  # Wird bei Änderung automatisch aktualisiert
```

**`backend/core/config.py`:**
```python
# Statt hart codiert:
# app_version: str = "2.0.0"

# Dynamisch aus VERSION-Datei:
def _get_version() -> str:
    version_file = Path(__file__).resolve().parent.parent.parent / "version"
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.0.0-dev"

class Settings(BaseSettings):
    app_version: str = _get_version()
```

**`backend/__init__.py`:**
```python
# Dynamisch geladen:
def _get_version() -> str:
    from pathlib import Path
    v = Path(__file__).resolve().parent.parent / "version"
    return v.read_text().strip() if v.exists() else "0.0.0-dev"

__version__ = _get_version()
```

**`backend/a2a/agent_card.py`:**
```python
from backend import __version__
# oder
from backend.core.config import settings
version = settings.app_version
```

**`backend/main.py` (Docstring):**
```python
"""FastAPI application entry point for Danwa v{settings.app_version}."""
```

---

## 3. Git-basierte Versionierung (optional, empfohlen)

Falls Git-Tags genutzt werden sollen:

```bash
# Neues Release taggen
git tag -a v1.1.0 -m "Modularisierung abgeschlossen"
git push origin v1.1.0
```

**Datei `version`** wird automatisch mit dem Tag synchronisiert:

```bash
# Pre-commit Hook oder CI-Skript
# Prüfe ob /version mit dem letzten Tag übereinstimmt
```

---

## 4. UI-Konsistenz

### 4.1 Im Frontend

```typescript
// In stores.ts oder einer neuen Datei: stores/version.ts
export const appVersion = writable<string>("");

// Beim App-Start (App.svelte oder +layout.ts):
onMount(async () => {
  const res = await fetch("/api/v1/config/version");
  const data = await res.json();
  appVersion.set(data.version);
});
```

**API-Endpoint:**
```python
# GET /api/v1/config/version
# → { "version": "1.1.0", "build": "2026-05-13T22:01:04+02:00" }
```

### 4.2 Version-Endpoint

```python
@router.get("/version")
async def get_version(settings: Settings = Depends(get_settings)):
    return {
        "version": settings.app_version,
        "build": build_timestamp,
        "commit": git_commit_hash,  # Optional, aus Umgebungsvariable
    }
```

### 4.3 Im Footer oder About-Dialog

```
Danwa v1.1.0
© 2026 Danwa Community
```

Statt überall verteilter Versionstexte wird nur **einmal** aus der API geladen.

---

## 5. Empfohlene Versionshistorie

| Version | Datum | Änderung |
|---------|-------|----------|
| 0.1.0 | 2025-xx-xx | Chainlit-Vorgänger (intern, nie veröffentlicht) |
| 0.9.0 | 2026-xx-xx | Neustart mit FastAPI + LangGraph, erste funktionsfähige Version |
| 1.0.0 | 2026-xx-xx | Erster offizieller Release (wenn gewünscht) |
| 1.1.0 | 2026-05-15 | Modularisierung: Module-Architektur + EN-SSOT |
| 1.2.0 | 2026-xx-xx | Übersetzungscache + Mehrsprachigkeit |
| 1.3.0 | 2026-xx-xx | Modulecosystem + GitHub-Repo |
| 2.0.0 | künftig | Breaking Change (z.B. neue DB-Struktur) |

> **Empfehlung:** Wir beißen nicht auf 2.0.0 an. Der aktuelle Stand ist ein stabiles
> 0.9.x / Pre-1.0 System. Die Modularisierung ist ein guter Anlass für **1.0.0**.

---

## 6. Build-Integration

### 6.1 Versionsstempel bei Build

```python
# In Makefile oder pyproject.toml [tool.uv.scripts]
version-stamp:
    python scripts/stamp_version.py

# scripts/stamp_version.py
#!/usr/bin/env python3
"""Stamp version from /version into build metadata."""
import json
from pathlib import Path

version = Path("version").read_text().strip()
build_info = {
    "version": version,
    "built_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
}
Path("src/backend/_build_info.json").write_text(json.dumps(build_info))
```

### 6.2 Frontend-Build

```json
// package.json
{
  "version": "1.1.0",
  "scripts": {
    "build": "vite build --mode production"
  }
}
```

Die Version wird dynamisch vom API bezogen, muss also **nicht** in `package.json` stehen.

---

## 7. Tests

- [ ] `test_version_consistency.py`: Prüft, dass `/version`-Endpoint, `pyproject.toml`,
  `backend/__init__.py` und `backend/core/config.py` alle dieselbe Version liefern
- [ ] Frontend-Test: Versionsnummer wird korrekt im UI angezeigt

---

## 8. Akzeptanzkriterien

- [ ] AC-1: **Eine einzige Datei** (`/version`) als Quelle der Wahrheit
- [ ] AC-2: Alle Backend-Komponenten lesen dynamisch daraus (nicht hart codiert)
- [ ] AC-3: `/api/v1/config/version` liefert konsistente Version
- [ ] AC-4: Frontend zeigt Version aus API an (kein Hardcoded)
- [ ] AC-5: Versionsänderung = eine Datei ändern (`/version`) → Rest automatisch
- [ ] AC-6: Kein Versions-Chaos mehr (kein Widerspruch zwischen UI, API und Docs)

---

## 9. Abhängigkeiten

- Keine — kann **jetzt** umgesetzt werden (parallel zu allen anderen Sprints)
- Wird von Sprint 4+ automatisch mitbenutzt (Service-LLM-Version in Health-Response etc.)
