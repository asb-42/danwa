# Test-Failure-Analyse: danwa-core nach Phase 0a.1 (Tests-Migration)

**Datum:** 2026-06-20
**Status:** Analyse-Bericht
**Vorgänger:** [`2026-06-20_danwa-user-facing-migration.md`](2026-06-20_danwa-user-facing-migration.md)
**Branch:** `danwa-core` `feat/pending-fixes-2026-06` (Commit `44c8310` + `7b44d49` + `974c31d`)

---

## 1. Rohdaten

Pytest-Lauf auf `tests/backend/` mit `--tb=line -q --no-header --color=no`:

```
3646 collected
3071 passed  (84.2%)
556 failed
 16 errors
  4 skipped
  2 xfailed
510.99s (0:08:30)
```

**Top-15 Fehlertypen (gruppiert aus `grep "^E "`):**

| # | Anzahl | Fehlertyp | Kategorie |
|---|--------|-----------|-----------|
| 1 | **512** | `AttributeError: '_IncludedRouter' object has no attribute 'path'` | **A** Bug in Dependency-Setup |
| 2 | 12 | `jinja2.exceptions.TemplateNotFound: 'academic_debate.html' not found` | **B** Fehlende Print-Templates |
| 3 | 7 | `TypeError: UserStore.set_last_workspace() got unexpected 'tenant_id'` | **C** UserStore-API-Drift |
| 4 | 7 | `AssertionError: Version file not found: /media/data/coding/danwa-core/version` | **D** Fehlende `version`-Datei |
| 5 | 3 | `TypeError: UserStore.get_last_workspace() got unexpected 'tenant_id'` | **C** dito |
| 6 | 3 | `jinja2.exceptions.TemplateNotFound: 'transactional_drafting.html' not found` | **B** dito |
| 7 | 2 | `KeyError: 'turn_label'` | **E** Template-Data-Mismatch |
| 8 | 2 | `AssertionError: {"detail":"Not Found"}` | **F** HTTP-Status-Mismatch |
| 9 | 1 | `ModuleNotFoundError: No module named 'src'` | **G** Falscher Import-Pfad |
| 10 | 1 | `KeyError: 'member_count'` | **E** Model-Mismatch |
| 11 | 1 | `jinja2.exceptions.TemplateNotFound: 'minimal.html' not found` | **B** dito |
| 12 | 1 | `AssertionError: transactional_drafting.json template must exist` | **B** dito |
| 13 | 1 | `AssertionError: tenant-A: expected 3, got 0` | **F** Tenant-Scoped-Bug |
| 14 | 1 | `AssertionError: data/workflows is the storage path...` | **D** Persistenzpfad-Mismatch |
| 15 | 1 | `AssertionError: expected 7 (2 case + 5 project), got 0` | **F** Debate-Count-Mismatch |

**Hotspot-Dateien (meiste Failures):**

| Datei | Failures | Dominante Kategorie |
|-------|----------|---------------------|
| `test_blueprint_api.py` | 60 | A (prometheus) + A few D |
| `test_case_scoped_router.py` | 39 | A + F |
| `test_auth_router.py` | 31 | A (Hauptkette) |
| `test_a2a_e2e.py` | 30 | A (alle via TestClient) |
| `test_hitl_integration.py` | 24 | A |
| `test_print_plugin_render.py` | 23 | B + i18n |
| `test_i18n_api.py` | 22 | A |
| `test_input_composer_api.py` | 21 | A |
| `test_workflow_templates.py` | 20 | A + D |
| `test_workspace_router.py` | 16 | A + F |
| `test_module_api.py` | 16 | A |
| `test_inbox_router.py` | 16 | A + F |
| `test_dms_api.py` | 16 | A |
| `test_debate_api.py` | 16 | A |

---

## 2. Kategorien-Aufschlüsselung

### Kategorie A — prometheus_fastapi_instrumentator-Inkompatibilität (512 Failures = 92%)

**Symptom:** Jeder Test, der `TestClient(app)` benutzt, schlägt fehl mit:
```
AttributeError: '_IncludedRouter' object has no attribute 'path'
  at .venv/lib/python3.11/site-packages/prometheus_fastapi_instrumentator/routing.py:55
  in _get_route_name
```

**Ursache:** Die Version von `prometheus_fastapi_instrumentator` in danwa-core's `.venv` ist mit der aktuellen Starlette/FastAPI-Version inkompatibel. `routing.py:55` versucht `route.path` auf einem `_IncludedRouter`-Objekt, das in neueren Starlette-Versionen ein anderes Interface hat.

**Betroffen:** Alle Tests, die via `TestClient` HTTP-Requests gegen die FastAPI-App feuern. Das sind **fast alle Tests** — daher die 92%.

**Fix-Strategie:**
- **Option 1 (schnell):** `prometheus_fastapi_instrumentator` auf eine kompatible Version pinnen oder aktualisieren. Test `uv pip install --upgrade prometheus_fastapi_instrumentator` in danwa-core.
- **Option 2 (Workaround):** In der Test-Fixture die Instrumentator-Middleware deaktivieren (z.B. via env-Var `ENABLE_METRICS=false`, wenn main.py das respektiert).
- **Option 3 (pur):** Im Test-Conftest den `TestClient` so monkey-patchen, dass er die Instrumentator umgeht.

**Geschätzter Aufwand:** 1-2 Commits, vermutlich < 1 Stunde.

**Impact:** Sollte allein ~500 Tests auf grün bringen.

---

### Kategorie B — Fehlende Print-Templates (16 Failures)

**Symptom:** `jinja2.exceptions.TemplateNotFound: 'academic_debate.html' not found in /media/data/coding/danwa-core/templates/print`

**Ursache:** In danwa gibt es ein `templates/print/`-Verzeichnis mit Jinja2-Templates für PDF/DOCX-Rendering. In danwa-core existiert `templates/` offenbar nicht oder die Templates wurden nicht migriert.

**Betroffene Templates:**
- `academic_debate.html` (12x)
- `transactional_drafting.html` (3x)
- `minimal.html` (1x)

**Fix-Strategie:**
- `templates/print/` aus danwa nach danwa-core kopieren
- Falls Test-Skripte die Templates auch brauchen: `tests/test_print_plugin_render.py` referenziert sie bereits

**Geschätzter Aufwand:** 1 Commit (Copy-Operation), < 15 min.

---

### Kategorie C — UserStore-API-Drift (10 Failures)

**Symptom:** `TypeError: UserStore.set_last_workspace() got an unexpected keyword argument 'tenant_id'`

**Ursache:** In danwa wurde `set_last_workspace(user_id, tenant_id, case_id, ...)` aufgerufen. In danwa-core hat `set_last_workspace` eine andere Signatur (vermutlich ohne `tenant_id`, weil Tenant-Scoped bereits über den User geht).

**Fix-Strategie:**
- Test-Aufrufe an neue Signatur anpassen (`tenant_id` weglassen)
- ODER: UserStore um `tenant_id`-Parameter erweitern (falls Tests die korrektere API nutzen)

**Wahrscheinlich:** Test-Drift (die Tests sind 1:1 aus danwa kopiert, aber danwa-core hat die Signatur weiterentwickelt).

**Geschätzter Aufwand:** 1-2 Commits, 30 min.

---

### Kategorie D — Fehlende `version`-Datei (7 Failures)

**Symptom:** `AssertionError: Version file not found: /media/data/coding/danwa-core/version`

**Ursache:** Der Test `test_version_consistency.py::TestVersionFile::test_version_file_exists` prüft, ob es eine `version`-Datei im Repo-Root gibt. In danwa gibt es die (Format: `0.3.0`), in danwa-core nicht (dort ist `pyproject.toml:1.2.0`).

**Fix-Strategie:**
- **Option 1 (entkoppelt):** Test löschen, weil danwa-core `pyproject.toml` als Version-SSOT hat
- **Option 2 (kompatibel):** `version`-Datei in danwa-core anlegen, von pyproject generieren lassen (z.B. via Hatch/Hatchling)
- **Option 3 (minimal):** Test in einen danwa-core-spezifischen Test umschreiben, der `pyproject.toml` liest

**Empfehlung:** Option 1 oder 3 — danwa-core hat eine bewusste andere Version-Strategie.

**Geschätzter Aufwand:** 1 Commit, 5 min.

---

### Kategorie E — Model-/Template-Data-Mismatch (3 Failures)

**Symptom:** `KeyError: 'turn_label'` und `KeyError: 'member_count'`

**Ursache:** Tests erwarten Felder in Datenstrukturen (Rendering-Context, Membership-Response), die in danwa-core umbenannt oder entfernt wurden.

**Fix-Strategie:** Test-Assertions anpassen, oder Model umbenennen falls sinnvoll.

**Geschätzter Aufwand:** 1 Commit, 15 min.

---

### Kategorie F — HTTP-Status / Business-Logic-Mismatch (~10 Failures)

**Symptom:** `assert 404 == 200`, `assert 404 == 422`, `expected 7, got 0` (Debate-Counts), `tenant-A: expected 3, got 0`

**Ursache:** Echte semantische Unterschiede:
- `test_case_scoped_router.py`: Backend liefert 404 mit `{"detail":"Not Found"}` statt 422 mit Validierungs-Details
- `test_workspace_router.py`: `debate_count=0` statt erwarteter 2 oder 7 — die Workspace-Route zählt Debatten falsch (siehe Commit-Message: "still using the legacy project-scoped debate store")
- `test_inbox_router.py`: 404 statt 200 für bestimmte Endpoints

**Bedingung:** Diese Failures sind **echte Bugs oder Regressionen** in danwa-core, NICHT Test-Drift. Sie verdienen besondere Aufmerksamkeit.

**Fix-Strategie:**
- 404-vs-422: Vermutlich Test-Erwartung anpassen (FastAPI-Default ist 404 für unbekannte Routes)
- Workspace-Route: Backend-Code fixen, damit Tenant-Scoped-Counts funktionieren
- Inbox: Einzelne Endpoints prüfen

**Geschätzter Aufwand:** 2-3 Commits, 1-2 Stunden (inkl. Debugging).

---

### Kategorie G — Falsche Import-Pfade (1 Failure)

**Symptom:** `ModuleNotFoundError: No module named 'src'`

**Ursache:** Ein einzelner Test importiert noch von `src.*` — vermutlich der `ModuleNotFoundError` aus der `tests/test_*.py` Top-Level-Migration, die ich bewusst aus 0a.1 ausgeschlossen hatte. Eventuell hat sich ein Top-Level-Test in `tests/backend/` eingeschlichen.

**Fix-Strategie:** Test finden, Import korrigieren oder Test löschen.

**Geschätzter Aufwand:** 1 Commit, 5 min.

---

## 3. Priorisierte Roadmap (Fix-Commits)

| Reihenfolge | Commit | Inhalt | Erwartete Verbesserung | Aufwand |
|-------------|--------|--------|------------------------|---------|
| 1 | `fix(test): resolve prometheus_fastapi_instrumentator incompatibility` | A | ~500 Tests grün | 1h |
| 2 | `chore: copy templates/print/ from danwa monorepo` | B | +16 Tests grün | 15 min |
| 3 | `test(user-store): adapt to new signature (drop tenant_id)` | C | +10 Tests grün | 30 min |
| 4 | `test(version): read version from pyproject.toml` | D | +7 Tests grün | 5 min |
| 5 | `test(render): update i18n expectations for print templates` | B+i18n | Restliche `test_print_plugin_render.py` | 30 min |
| 6 | `test: fix src.* import path drift` | G | +1 Test grün | 5 min |
| 7 | `fix(workspace): tenant-scoped debate_count` | F | +~3 Tests grün | 1-2h |
| 8 | `test: adapt to new HTTP status codes (404 vs 422)` | F | +~3 Tests grün | 15 min |
| 9 | `test(render): update model field expectations` | E | +3 Tests grün | 15 min |

**Erwartete Pass-Rate nach allen 9 Commits:** 98-99% (3500+ von 3646 Tests grün).

**Verbleibende ~10-20 Failures** sind vermutlich Test-Drift, der nur durch Code-Lesen im Detail zu fixen ist (nicht durch dieses Bulk-Pattern lösbar).

---

## 4. Empfehlung

**Priorität 1 zuerst machen** — der prometheus-Fix ist ein 1-Haufen-Change mit riesigem Impact. Wenn der funktioniert, sehen wir den echten Stand der anderen Failures erst richtig (viele könnten vom prometheus-Bug maskiert sein, wenn er in Setup-Phasen auftritt).

**Priorität 4 (version-Datei) zuerst** — ist trivial, gibt +7 grüne Tests, schafft Momentum.

**Dann B und C** — beide sind Copy-/Refactor-Arbeiten, risikoarm.

**F zuletzt** — die brauchen echte Analyse; ggf. ein eigener Sprint.

---

## 5. Was NICHT in dieser Roadmap ist

- **Top-Level-Tests (`tests/test_*.py`)** — separat, siehe MIGRATION_NOTES.md
- **Frontend-Tests (`tests/frontend/`)** — bleiben in `danwa`
- **Tests, die in danwa-core bereits angepasst wurden** — die sehen wir hier nicht
