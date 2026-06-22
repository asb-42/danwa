# Plan: `danwa-core` Backend-Test-Migration

**Datum:** 2026-06-21
**Status:** ✅ **Abgeschlossen** (2026-06-21)
**Vorgänger:** [`2026-06-20_danwa-user-facing-migration.md`](2026-06-20_danwa-user-facing-migration.md) §1b.5, Commit `44c8310` (Phase 0a.1), Commits `8ad35d0`/`2f6876e`/`d2b7cc8` (Test-Cleanup)
**Repos:** `danwa` (dieses), `danwa-core` (extern)
**Scope:** Source-Modul-Migration + Test-Migration für 26 Backend-Tests

---

## 0. Abschluss-Status

Der Plan wurde am 2026-06-21 vollständig umgesetzt und auf `main` gemerged:

| Phase | Commit in `danwa-core` | Commit in `danwa` | Ergebnis |
|-------|-----------------------|-------------------|----------|
| Phase 1 (Source-Module portieren) | `2cd40cd` (Branch `feat/src-core-dms-tools-migration-2026-06`) | — | Source-Module in `danwa-core` |
| Phase 2 (Tests portieren) | `2cd40cd` (gleicher Commit) | — | **183 passed / 52 skipped / 0 failed** in `danwa-core` |
| Phase 3 (Cleanup `danwa`) | — | `c5c6091` `test(backend): remove 26 backend tests now living in danwa-core` (-3411 Zeilen) | 26 Duplikate entfernt |
| Phase 4 (PR + Merge) | — | `e4ca5de` `merge: Phase 1.4 Backend Test Cleanup` | Auf `main` gemerged |

**Verifikationskriterien — alle erfüllt:**

- ✅ Alle 26 migrierten Tests grün in `danwa-core` (183 passed / 52 skipped / 0 failed)
- ✅ Bestehende Tests in `danwa-core` weiterhin grün
- ✅ `danwa` Frontend-Build weiterhin grün (Vitest 220/220, Playwright 154)
- ✅ `danwa/tests/` von 171 auf 144 Dateien reduziert
- ✅ Beide Repos haben klaren Push-Stand (`danwa`: `c5c6091`/`e4ca5de` auf `main`; `danwa-core`: Branch `feat/src-core-dms-tools-migration-2026-06` Commit `2cd40cd`)
- ✅ Working-Tree in `danwa` clean (`git status`: "nichts zu committen, Arbeitsverzeichnis unverändert")

**Folge-Themen (nicht in diesem Plan, separat zu prüfen):**

- Die Source-Module unter `danwa/src/{core,dms,tools}/` sind weiterhin im `danwa`-Repo vorhanden und werden teilweise noch genutzt (u.a. `backend/api/routers/sessions.py` importiert `src.core.debate_engine`, `src.core.session_db`, `src.core.trace_logger`, `src.tools.report_generator`). Diese Legacy-Pfade sind **nicht** Teil dieses Plans, sollten aber in einem separaten Aufräum-Plan migriert werden, sobald `danwa-core` die letzte `src.*`-Referenz sauber übernehmen kann.


---

## 1. Ziel

26 Backend-Pytest-Dateien aus `danwa/tests/` nach `danwa-core/tests/backend/` migrieren. Diese Tests können derzeit **nicht** migriert werden, weil sie auf Source-Module in `danwa/src/{core,dms,tools}/` zugreifen, die **in `danwa-core` (noch) nicht existieren**. Konsequenzen heute:

- `danwa/tests/` enthält 171 Pytest-Dateien, davon **143 sind bereits in `danwa-core/tests/backend/`** (Phase 0a.1, Commit `44c8310`).
- Die verbleibenden **28 Tests** in `danwa` testen Source-Code, der nur im `danwa`-Monorepo lebt.
- Eine direkte Migration der Test-Dateien erzeugt nur `ModuleNotFoundError: No module named 'src'` — siehe `plans/2026-06-20_danwa-user-facing-migration.md` §1b.5.

**Lösung:** Zuerst die Source-Module portieren, dann die Tests.

---

## 2. Inventur

### 2.1 Source-Module in `danwa`, die nach `danwa-core` müssen

**`src/core/` (8 Dateien, 814 LoC):**

| Datei | LoC | Pfad in `danwa` | Zielpfad in `danwa-core` | Tests die darauf warten |
|-------|-----|-----------------|---------------------------|-------------------------|
| `debate_engine.py` | 314 | `src/core/debate_engine.py` | `backend/core/debate_engine.py` | `test_debate_engine.py`, `test_memory.py`, `test_session_db.py` |
| `trace_logger.py` | 50 | `src/core/trace_logger.py` | `backend/core/trace_logger.py` | `test_trace_logger.py`, `test_debate_engine.py` |
| `llm_router.py` | 95 | `src/core/llm_router.py` | `backend/core/llm_router.py` | `test_llm_router.py` |
| `logging_config.py` | 32 | `src/core/logging_config.py` | `backend/core/logging_config.py` | `test_logging_config.py` |
| `memory.py` | 82 | `src/core/memory.py` | `backend/core/memory.py` | `test_memory.py` |
| `privacy.py` | 39 | `src/core/privacy.py` | `backend/core/privacy.py` | `test_privacy.py` |
| `prompt_manager.py` | 85 | `src/core/prompt_manager.py` | `backend/core/prompt_manager.py` | `test_prompt_manager.py`, `test_prompt_manager_dms.py` |
| `session_db.py` | 117 | `src/core/session_db.py` | `backend/core/session_db.py` | `test_session_db.py`, `test_dms_database.py` |

**`src/dms/` (3 von 14 Dateien fehlen in `danwa-core/services/dms/`):**

| Datei | LoC | Pfad in `danwa` | Zielpfad in `danwa-core` | Tests die darauf warten |
|-------|-----|-----------------|---------------------------|-------------------------|
| `dms.py` | 187 | `src/dms/dms.py` | `backend/services/dms/dms.py` | `test_dms_core.py`, `test_dms_core_comprehensive.py`, `test_dms_memory.py` |
| `dms_memory.py` | 45 | `src/dms/dms_memory.py` | `backend/services/dms/dms_memory.py` | `test_dms_memory.py`, `test_dms_core_comprehensive.py` |
| `project_manager.py` | 43 | `src/dms/project_manager.py` | `backend/services/dms/project_manager.py` | `test_dms_project_manager.py`, `test_dms_core_comprehensive.py` |

Die übrigen 11 Dateien in `src/dms/` existieren bereits in `danwa-core/backend/services/dms/` (siehe Inventur).

**`src/tools/` (1 von 4 Dateien fehlt):**

| Datei | LoC | Pfad in `danwa` | Zielpfad in `danwa-core` | Tests die darauf warten |
|-------|-----|-----------------|---------------------------|-------------------------|
| `doc_parser.py` | 67 | `src/tools/doc_parser.py` | `backend/tools/doc_parser.py` | `test_doc_parser.py` |

(`tools/`-Verzeichnis existiert noch nicht in `danwa-core/backend/` — muss neu angelegt werden.)

### 2.2 Cross-Modul-Imports (zu fixen beim Portieren)

**`src/dms/dms_memory.py`** → `from .dms import DMS` (relativ, funktioniert auch in neuem Ort).

**`src/core/debate_engine.py`** → `from src.tools.web_search import WebSearchTool, extract_json_list` (Cross-package!). `tools/web_search.py` ist **nicht** in der Plan-Liste (von keinem der 26 Tests angefordert). WebSearchTool wird zur Laufzeit geladen — beim Portieren entweder:
- (a) `web_search.py` mit-portieren als zusätzliche Abhängigkeit, oder
- (b) `web_search`-Import in `debate_engine.py` durch Dependency-Injection entkoppeln (empfohlen).

**`src/dms/document_processor.py`** → `from src.tools.doc_parser import DocumentParser` (auch Cross-package). Da wir `doc_parser.py` mit-portieren, muss `document_processor.py` entsprechend seinen Import auf `backend.tools.doc_parser` umstellen.

**`src/dms/rag_pipeline.py`** → interne `src.dms.*`-Imports (relativ — bleibt unverändert).

**`src/dms/document_processor.py`** → externe `from src.tools.doc_parser import DocumentParser` (s.o.).

**`src/__init__.py`** → re-exportiert `src.dms.*`. **Vorsicht:** dieser `__init__.py` macht den `src`-Namespace öffentlich — beim Portieren als `backend/__init__.py` müssen alle Re-Exports umgeschrieben werden.

**`src/dms/__init__.py`** → `from src.tools.doc_parser import DocumentParser` (Cross-package). Muss beim Portieren angepasst werden.

### 2.3 Bestehende `danwa-core/backend/core/` Dateien (nicht überschreiben!)

| Datei | Status |
|-------|--------|
| `config.py` | bleibt |
| `logging.py` | bleibt — Achtung: Namens-Kollision mit `logging_config.py`! Importer müssen angepasst werden. |
| `llm_id_aliases.py` | bleibt |
| `profiles.py` | bleibt |
| `security.py` | bleibt |
| `seed.py` | bleibt |

### 2.4 Tests, die portiert werden (26 Dateien)

**`tests/` (root, 24 Dateien):**
- `test_debate_engine.py`
- `test_dms_chunker.py`
- `test_dms_config.py`
- `test_dms_core.py`
- `test_dms_core_comprehensive.py`
- `test_dms_database.py`
- `test_dms_document_processor.py`
- `test_dms_hybrid_retriever.py`
- `test_dms_memory.py`
- `test_dms_metadata_index.py`
- `test_dms_project_manager.py`
- `test_dms_rag_formatter.py`
- `test_dms_rag_pipeline.py`
- `test_dms_vector_store.py`
- `test_doc_parser.py`
- `test_i18n_service.py`
- `test_llm_router.py`
- `test_logging_config.py`
- `test_memory.py`
- `test_paddleocr_integration.py`
- `test_privacy.py`
- `test_prompt_manager.py`
- `test_prompt_manager_dms.py`
- `test_rag_pipeline_retrieval.py`
- `test_session_db.py`
- `test_trace_logger.py`

**Hinweis:** `test_dms_vector_store.py`, `test_dms_document_processor.py`, `test_i18n_service.py`, `test_paddleocr_integration.py` importieren **keine** `src.*`-Module direkt — sie sind nur indirekt über die importierten Module abhängig. Sie sollten trotzdem migriert werden für Vollständigkeit.

---

## 3. Vorgehen

### 3.1 Branch-Strategie

| Repo | Branch | Basis |
|------|--------|-------|
| `danwa-core` | `feat/src-core-dms-tools-migration-2026-06` | `origin/main` |
| `danwa` | `feat/phase2-test-migration-followup` | `feat/phase2-user-facing-only` |

### 3.2 Reihenfolge (jeder Schritt einzeln lauffähig + testbar)

| # | Schritt | Repo | Commit-Typ |
|---|---------|------|------------|
| 1 | **Source-Module kopieren** — `src/core/*` (8) + `src/dms/{dms,dms_memory,project_manager}.py` (3) + `src/tools/doc_parser.py` (1) + `src/tools/__init__.py` (neu) → `danwa-core/backend/{core,services/dms,tools}/`. Bestehende `backend/core/{config,logging,security,…}.py` nicht überschreiben. | `danwa-core` | `feat(backend): import 12 src/ modules from danwa monorepo` |
| 2 | **Import-Pfade umschreiben** in den 12 portierten Modulen: `from src.X` → `from backend.X`, `from .X` (relativ) bleibt. Achtung: `src/core/debate_engine.py` importiert `src.tools.web_search` — diese Cross-Dependency muss entweder mit-portiert werden (zusätzlich `web_search.py`) oder der Import wird durch DI entkoppelt. Empfehlung: **Phase A2a zuerst mit-portieren** für minimale Diff-Komplexität. | `danwa-core` | (in Commit 1) |
| 3 | **Import-Konflikte auflösen** — `src/core/logging_config.py` enthält `setup_logging()` und `JSONFormatter`. `danwa-core/backend/core/logging.py` enthält bereits ein `setup_logging()`. **Lösung:** `logging_config.py` umbenennen zu `trace_logging.py` (spezifischer Name, keine Kollision). Oder: Imports in den Test-Dateien anpassen, dass sie `from backend.core.logging_config import ...` nutzen, aber in `danwa-core` einen Re-Export in `backend/core/logging.py` einrichten. **Empfehlung:** Umbenennen ist sauberer. | `danwa-core` | (in Commit 1) |
| 4 | **Tests kopieren** — 26 Test-Dateien aus `danwa/tests/` → `danwa-core/tests/backend/` (1:1 kopieren). | `danwa-core` | `test(backend): migrate 26 test files from danwa monorepo` |
| 5 | **Test-Import-Pfade umschreiben** — `from src.X` → `from backend.X` in allen 26 Test-Dateien (Datei-intern + alle Imports). | `danwa-core` | (in Commit 4) |
| 6 | **Tests ausführen** — `cd danwa-core && uv run pytest tests/backend/test_{alle 26} -v --tb=short`. Probleme fixen (häufig: `import src.X` in Helper-Modulen, falsche Pfade in conftest, fehlende `__init__.py`). | `danwa-core` | (in Commit 4 oder Folge-Commits) |
| 7 | **In `danwa`** — alte Test-Dateien löschen (Commit 4 in `danwa`-Branch). | `danwa` | `test(backend): remove 26 migrated tests (now in danwa-core)` |
| 8 | **Smoke-Test** in `danwa` — sicherstellen, dass die Source-Module weiterhin via `src.*` funktionieren (kein Frontend-Build-Bruch). `cd frontend && npm run build` + `uv run pytest tests/` (lokale Suite). | `danwa` | (in Commit 7 oder neu) |

### 3.3 Risiken und Sonderfälle

| Risiko | Impact | Mitigation |
|--------|--------|------------|
| **`tools/web_search.py`** (Cross-Dependency von `debate_engine.py`) | Build-Bruch in `danwa-core` | Entweder mit-portieren (Phase A2a) oder via `TYPE_CHECKING` + Dependency-Injection entkoppeln |
| **Namens-Kollision `logging_config.py` vs. `logging.py`** in `danwa-core/backend/core/` | Import-Fehler in Tests | Umbenennen zu `trace_logging.py` in Commit 1 |
| **`src/dms/dms.py`** hat **sehr wahrscheinlich** weitere Imports aus `src.*` (private helpers) | Lange Diff-Liste | Phase 1 mit `--name-only`-Diff gegen `danwa-core` prüfen |
| **`src/dms/dms.py` ist ein Hauptmodul** (187 LoC) — wahrscheinlich komplex | Mehrere Folge-Commits nötig | Schrittweise portieren, in Commit 1 nur die Datei + grobe Fixes, in Commit 2-3 Detail-Fixes |
| **`__init__.py`-Re-Exports** in `src/`, `src/core/`, `src/dms/`, `src/tools/` | Public API | Komplett-Re-Write dieser `__init__.py`-Dateien in Commit 1 — gründlich testen |
| **Tests benutzen ggf. `tmp_path`, `monkeypatch`, `conftest.py`-Fixtures** aus `danwa-core/tests/backend/conftest.py` | Test-Inkompatibilitäten | conftest aus `danwa-core` muss alle nötigen Fixtures liefern (existieren bereits für die 143 migrierten Tests) |
| **`src/core/prompt_manager.py`** hat 2 Tests (`test_prompt_manager`, `test_prompt_manager_dms`) | Test-Konflikt wenn beide dasselbe `PromptManager` testen | Vermutlich Harmlos — die Tests decken verschiedene Aspekte ab |

### 3.4 Verifikationskriterien

| Kriterium | Test |
|-----------|------|
| Alle 26 migrierten Tests grün | `cd danwa-core && uv run pytest tests/backend/test_{debate_engine,trace_logger,llm_router,logging_config,memory,privacy,prompt_manager,session_db,dms_chunker,dms_config,dms_core,dms_core_comprehensive,dms_database,dms_document_processor,dms_hybrid_retriever,dms_memory,dms_metadata_index,dms_project_manager,dms_rag_formatter,dms_rag_pipeline,dms_vector_store,doc_parser,i18n_service,privacy,paddleocr_integration,prompt_manager,prompt_manager_dms,rag_pipeline_retrieval,session_db} -v` zeigt 0 failures |
| Bestehende 143 Tests in `danwa-core` weiterhin grün | `cd danwa-core && uv run pytest tests/backend -q --tb=no` zeigt keine neuen Failures |
| `danwa` Frontend-Build weiterhin grün | `cd danwa/frontend && npm run build` exit 0 |
| `danwa/tests/` nach Cleanup bei ~145 Dateien (vorher 171) | `find danwa/tests -name 'test_*.py' | wc -l` ≈ 145 |

---

## 4. Commit-Reihenfolge (Empfehlung)

```
# 1) Source-Module portieren + Import-Pfade fixen + Kollisionen auflösen
#    in einem großen Commit (atomar, sonst baut danwa-core nicht)
danwa-core: feat(backend): import 12 src/ modules from danwa monorepo (Phase 1)

# 2) Tests portieren + Import-Pfade fixen + ggf. Detail-Fixes
danwa-core: test(backend): migrate 26 test files from danwa monorepo (Phase 2)
danwa-core: test(backend): fixup imports/conftest for migrated tests (Phase 2.1)
danwa-core: test(backend): rename logging_config → trace_logging to avoid clash (Phase 2.2)
danwa-core: chore(release): bump version + CHANGELOG (Phase 3)

# 3) danwa aufräumen
danwa: test(backend): remove 26 tests now living in danwa-core (Phase 4)
danwa: docs(plans): update with danwa-core test migration status (Phase 5)

# 4) PRs + Push + Review
```

---

## 5. Was bewusst NICHT in diesem Plan enthalten ist

- **`src/tools/web_search.py`**: Falls die DI-Entkopplung in `debate_engine.py` zu invasiv ist, würde ich **zuerst** `web_search.py` mit-portieren in einem **eigenen Commit** + ADR. Das ist eine **eigene Entscheidung**, die vom Review des ersten Commits abhängt.
- **`src/tools/{report_generator,web_search,custom_embedding}.py`** und andere nicht-Plan-Tests (`test_paddleocr_integration`, `test_i18n_service`, `test_dms_vector_store`, `test_dms_document_processor`): werden mit-migriert, weil sie zur Source-Modul-Familie gehören, aber brauchen ggf. zusätzliche externe Abhängigkeiten (PaddleOCR, i18n-Module). Falls diese Tests in `danwa-core` nicht laufen, sollten sie als `@pytest.mark.skip(reason="…")` markiert werden mit Hinweis auf die fehlende Dependency.
- **Frontend-Tests in `danwa-core`**: Nicht relevant — `danwa-core` ist Backend-only.
- **`src/services/`-Module in `danwa`**: Die meisten sind schon in `danwa-core/backend/services/`. Falls Lücken auftauchen, eigener Plan.
- **Refactoring der portierten Source-Module** (z.B. Dependency-Injection, Type Hints modernisieren): **Nicht** im Scope. Ziel ist 1:1-Migration mit minimalen Änderungen.

---

## 6. Erfolgskriterien

| Kriterium | Messbar |
|-----------|---------|
| Alle 12 Source-Module in `danwa-core` vorhanden und importierbar | `find danwa-core/backend/{core,services/dms,tools} -name 'debate_engine.py' -o -name 'trace_logger.py' ...` findet alle |
| Alle 26 Tests in `danwa-core/tests/backend/` grün | `pytest` Exit 0 für die 26 Files |
| Bestehende Tests in `danwa-core` (143) weiterhin grün | `pytest tests/backend` Exit 0 |
| `danwa` Frontend-Build weiterhin grün | `npm run build` Exit 0 |
| `danwa/tests/` reduziert von 171 auf ~145 | `find tests -name 'test_*.py' | wc -l` |
| Beide Repos haben einen klaren Push-Stand | Commits auf GitHub sichtbar, PRs erstellt |

---

## 7. Nicht-Ziele

- Generalüberholung der portierten Source-Module (Modernisierung, Type Hints, Async-Conversions)
- Entfernung von `src/` aus `danwa` komplett (es ist weiterhin das User-Repo mit eigener Backend-Legacy-Schicht)
- Aufsetzen von Tests in `danwa-studio`
- Performance-Optimierungen in den portierten Source-Modulen
- CI/CD-Anpassungen (z.B. Coverage-Reports für `danwa-core`)

---

## 8. Zeitplan (Schätzung)

```
Phase 1 (Source-Module portieren): 1–2 Tage
Phase 2 (Tests portieren):         1 Tag
Phase 3 (Cleanup danwa):           0.5 Tage
Phase 4 (Review + PRs):            0.5 Tage

Gesamt: ~3–4 Tage
```

---

## 9. Vorbedingungen

1. ✅ Phase 0a abgeschlossen (Plan [`2026-06-20_danwa-user-facing-migration.md`](2026-06-20_danwa-user-facing-migration.md))
2. ✅ User-Facing-Migration Phase 1–11 abgeschlossen (Commits `4552076`–`13f4a7b` + Test-Cleanup `d2b7cc8`, `8ad35d0`, `2f6876e`)
3. ✅ Alle drei Repos gepusht: `danwa`, `danwa-core`, `danwa-studio`
4. Vor Beginn: frischen `git fetch` in allen drei Repos, Working-Trees clean
