# Plan: Legacy `sessions`-Router in `danwa` aufräumen

**Datum:** 2026-06-22
**Status:** Entwurf (zur Abstimmung)
**Vorgänger:** [`2026-06-21_danwa-core-test-migration.md`](2026-06-21_danwa-core-test-migration.md) §0 (Abschluss-Status, Folge-Thema)
**Repos:** `danwa` (dieses), `danwa-core` (extern, Referenz)
**Scope:** Legacy-`src.*`-Imports in `backend/api/routers/sessions.py` entfernen — durch Deaktivierung des Routers, analog zu `danwa-core`.

---

## 1. Ausgangslage

### 1.1 Problem

[`backend/api/routers/sessions.py`](backend/api/routers/sessions.py:1) (119 Zeilen) ist die **einzige** Datei in `danwa/backend/`, die noch `src.*`-Imports enthält:

```python
# backend/api/routers/sessions.py:8-11
from src.core.debate_engine import DebateState
from src.core.session_db import SessionDB
from src.core.trace_logger import TraceLogger
from src.tools.report_generator import ReportGenerator
```

Diese Cross-Repo-Dependency ist die letzte offene Legacy-Brücke zu den `src/{core,dms,tools}/`-Modulen, die im Plan `2026-06-21_danwa-core-test-migration.md` §0 explizit als **Folge-Thema (separater Plan)** markiert wurde.

### 1.2 Vorbild `danwa-core`: So wurde es dort bereits gelöst

Im Schwester-Repo [`danwa-core/backend/api/routers/sessions.py`](../../danwa-core/backend/api/routers/sessions.py:1) liegt exakt dieselbe Datei (119 Zeilen, gleiche `src.*`-Imports), aber sie ist im Router-Layer **deaktiviert**:

```python
# danwa-core/backend/main.py:54
    # sessions,  # Legacy - superseded, removed for OpenAPI export
```

```python
# danwa-core/backend/main.py:498
    # app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])  # Legacy
```

In `danwa` ist die Registrierung **noch aktiv**:

```python
# danwa/backend/main.py:52
    sessions,
```

```python
# danwa/backend/main.py:511
    app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
```

### 1.3 Warum der Router überhaupt noch da ist — und warum er weg kann

| Evidenz | Befund |
|---|---|
| Frontend-Calls auf `/api/v1/sessions` | **Keine direkten Calls.** [`frontend/src/lib/api/session.js`](frontend/src/lib/api/session.js:1) nutzt stattdessen `/api/v1/workflow-exec/sessions` |
| Tests, die `sessions.router` importieren | **Keine** (nur Erwähnung in `test_report_generator_legacy.py`) |
| Deprecation-Hinweis in `danwa/backend/main.py:470` | `"Use /api/v1/tenants/{tid}/cases/{cid}/sessions/ instead."` |
| Deprecation-Hinweis in `danwa-core/backend/main.py:457` | identisch — Router in `danwa-core` ist disabled |
| Funktionaler Ersatz | [`backend/api/routers/assistant.py`](backend/api/routers/assistant.py:59) (`/api/v1/sessions` als Tenant-Scope), [`backend/api/routers/workflow_reports.py`](backend/api/routers/workflow_reports.py:156) (Report-Generation), [`backend/api/routers/workflow_exec.py`](backend/api/routers/workflow_exec.py:1) (Session-Liste via `/api/v1/workflow-exec/sessions`) |

**Schluss:** Der Router ist **toter Code** — er wird nirgends mehr produktiv aufgerufen, alle Funktionalität ist über moderne, case-scoped Routers abgedeckt.

### 1.4 Was NICHT in diesem Plan enthalten ist

- `src/{core,dms,tools}/`-Verzeichnisse werden **nicht** gelöscht. Sie werden weiterhin von `backend/api/routers/sessions.py` benutzt (vor diesem Plan), und `tests/backend/test_report_generator_legacy.py` referenziert `src.tools.report_generator` testweise. Erst nach erfolgreicher Deaktivierung von `sessions.py` kann in einem **Folge-Plan** die `src/*`-Source-Code-Bereinigung beginnen.
- `src/core/debate_engine.py` selbst wird nicht portiert oder umgeschrieben — Plan-Schwester [`2026-06-21_danwa-core-test-migration.md`](2026-06-21_danwa-core-test-migration.md) hat bereits die wichtigsten Source-Module nach `danwa-core` portiert; die Legacy-Pfade bleiben aus Stabilitätsgründen unangetastet.

---

## 2. Vorgehen

### 2.1 Branch-Strategie

| Repo | Branch | Basis |
|------|--------|-------|
| `danwa` | `chore/remove-legacy-sessions-router-2026-06` | `origin/main` |

### 2.2 Reihenfolge (jeder Schritt einzeln lauffähig + testbar)

| # | Schritt | Datei(en) | Commit-Typ |
|---|---------|-----------|------------|
| 1 | **Import-Statement auskommentieren** in `sessions.py` (analog zu `danwa-core`) — sofort sichtbar, dass die Datei nicht mehr lädt. Hinzufügen eines Module-Docstring-Updates: `"Legacy router — siehe main.py:511 für Status."` | `backend/api/routers/sessions.py` | `chore(backend): mark sessions router as legacy (imports disabled)` |
| 2 | **`sessions` aus `main.py`-Importliste auskommentieren** und Include-Aufruf auskommentieren (genau wie `danwa-core`). Deprecation-Hinweis `/api/v1/sessions` in `main.py:470` **bleibt** (Middle ware nutzt ihn). | `backend/main.py` | `chore(backend): disable legacy /api/v1/sessions router registration` |
| 3 | **Smoke-Test**: Backend lokal starten, `curl -I http://localhost:8000/api/v1/sessions` muss `X-Deprecation`-Header liefern und keinen 500er mehr werfen (durch die Deaktivierung fällt der Router weg, die Middleware antwortet mit 404). | (manuell) | (im Commit 2) |
| 4 | **Test-Suite lokal** ausführen: `uv run pytest tests/backend --collect-only -q` — Erwartung: keine neuen Failures. Vitest/E2E-Build: `cd frontend && npm run build` — Exit 0. | (manuell) | (im Commit 2 oder neu) |
| 5 | **Optional — Aufräum-Commit**: Wenn Schritt 3+4 grün sind, könnte `backend/api/routers/sessions.py` in einem **separaten Folge-Commit** gelöscht werden. **Empfehlung: NICHT** in diesem Plan — die Datei dokumentiert die Legacy-Schnittstelle für künftige Migrationen. | — | (separater Folge-Plan) |

### 2.3 Risiken und Sonderfälle

| Risiko | Impact | Mitigation |
|--------|--------|------------|
| **Frontend-Code, der doch `/api/v1/sessions` ruft** (z.B. vergessenes Hardcoding) | 404 statt 200/204 | Smoke-Test + grep `frontend/src` für `api/v1/sessions\b` — Befund aktuell: nur in [`session.js`](frontend/src/lib/api/session.js:1) als Sub-String (`workflow-exec/sessions`), kein Match |
| **`tests/backend/test_report_generator_legacy.py`** importiert `src.tools.report_generator` direkt — ist NICHT von der Router-Deaktivierung betroffen, aber wirft beim Sammeln weiterhin `ModuleNotFoundError`, wenn `src/` nicht im `pythonpath` ist | Test-Failure | Prüfen: ist `src/` heute schon im `pythonpath`? Wenn nein → entweder nachziehen oder Test explizit `@pytest.mark.skip(reason="legacy src.* reference")` markieren (analog zum PaddleOCR-Test) |
| **Andere Backend-Module**, die `src.*` indirekt via `sessions.py` läuten — bricht durch Deaktivierung | Build-Failure | Grep `from src.` über `backend/` → aktuell **nur** `sessions.py:8-11` und **`src/__init__.py`-Re-Exports**. Nach Commit 2 keine aktiven Imports mehr. |
| **Deprecation-Middleware** in `main.py:467-470` referenziert `/api/v1/sessions` weiterhin — das ist OK und gewollt: Clients sehen den `X-Deprecation`-Header und werden zum neuen Endpunkt geleitet | keins | Middleware bleibt unverändert |
| **`sessions` in `KNOWN_ISSUES.md` / `CHANGELOG.md`** dokumentieren | Drift | Eintrag in CHANGELOG: `"Removed legacy /api/v1/sessions router (superseded by /api/v1/workflow-exec/sessions and /api/v1/tenants/{tid}/cases/{cid}/sessions/)"` |

### 2.4 Verifikationskriterien

| Kriterium | Test |
|-----------|------|
| `sessions` ist aus `main.py:25-52` auskommentiert | `grep -n 'sessions' backend/main.py | head -5` zeigt `    # sessions,` |
| `include_router(sessions...)` ist auskommentiert | `grep -n 'sessions.router' backend/main.py` zeigt nur den auskommentierten Kommentar |
| Backend startet ohne Fehler | `uv run uvicorn backend.main:app --port 8001` → `200 OK` auf `/health` |
| `GET /api/v1/sessions` → 404 (nicht mehr registriert) | `curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/api/v1/sessions` → `404` |
| `GET /health` → 200 | wie oben |
| Bestehende Tests grün | `cd danwa-core && uv run pytest tests/backend -q --tb=no` exit 0; `cd frontend && npm run build` exit 0; `cd danwa && uv run pytest tests/backend --collect-only -q` exit 0 |

---

## 3. Commit-Reihenfolge (Empfehlung)

```bash
# 1) Legacy-Markierung in der Router-Datei (sichtbar, lokal testbar)
danwa: chore(backend): mark sessions router as legacy (imports disabled)

# 2) Router-Registrierung in main.py deaktivieren (analog danwa-core)
danwa: chore(backend): disable legacy /api/v1/sessions router registration

# 3) CHANGELOG-Eintrag
danwa: docs(changelog): note removal of legacy /api/v1/sessions router

# 4) PR öffnen, reviewen, mergen
```

**Bewusst NICHT in diesem Plan:**

- Löschen von `backend/api/routers/sessions.py` — könnte später in eigenem Plan erfolgen, wenn die `src/*`-Source-Module komplett aus `danwa` entfernt sind.
- Löschen der `src/{core,dms,tools}/`-Module — separater, deutlich invasiverer Folge-Plan.
- Refactoring der `assistant.py`-/`workflow_exec.py`-/`workflow_reports.py`-Routers — out of scope.

---

## 4. Erfolgskriterien

| Kriterium | Messbar |
|-----------|---------|
| `sessions` aus `main.py` Import + Registrierung auskommentiert | `grep -E '^\s+sessions\b' backend/main.py` zeigt nur Kommentar |
| `backend/api/routers/sessions.py` zeigt klar Legacy-Status | Docstring aktualisiert, Imports auskommentiert |
| Backend startet ohne `ImportError` von `src.*` | `uvicorn backend.main:app` exit 0 |
| `GET /api/v1/sessions` → 404 mit `X-Deprecation`-Header | `curl -I /api/v1/sessions` |
| Bestehende Test-Suite unverändert grün | `pytest`, `vitest`, `playwright` exit 0 |
| CHANGELOG aktualisiert | Eintrag unter `## [Unreleased]` |

---

## 5. Nicht-Ziele

- Vollständige Entfernung der `src/*`-Module aus `danwa`.
- Refactoring der case-scoped Routers in `assistant.py`/`workflow_exec.py`.
- Migration der `test_report_generator_legacy.py` (die Datei bleibt als Doku-Test bestehen).
- CI/CD-Anpassungen.

---

## 6. Zeitplan

```
Schritt 1-2 (Commits):  15 Minuten
Schritt 3 (Smoke-Test): 10 Minuten
Schritt 4 (CHANGELOG):   5 Minuten
PR-Review + Merge:     je nach Reviewer

Gesamt: ~30 Minuten + Review-Zeit
```

---

## 7. Vorbedingungen

1. ✅ Plan [`2026-06-21_danwa-core-test-migration.md`](2026-06-21_danwa-core-test-migration.md) ist abgeschlossen
2. ✅ `danwa` Working-Tree clean, auf `main`
3. ✅ Schwester-Repos `danwa-core`, `danwa-studio`, `danwa-modules` sind lokale Klone unter `/media/data/coding/`
4. Vor Beginn: `git fetch` + Working-Tree clean