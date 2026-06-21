# Plan: Reaktivierung der 7 `@pytest.mark.skip`-markierten Tests aus der danwa-core Test-Migration

**Datum:** 2026-06-21
**Status:** Entwurf (zur Abstimmung)
**Vorgänger:** [`2026-06-21_danwa-core-test-migration.md`](2026-06-21_danwa-core-test-migration.md), Commit `2cd40cd` (Phase 2), Commits `7050cc5` und `122be87` (Merges nach `danwa-core/main`)
**Repos:** `danwa-core` (extern)
**Branch-Vorbereitung:** `feat/skip-test-reactivation-2026-06`

---

## 1. Ziel

7 Test-Files, die während der Phase-2-Test-Migration (Commit `2cd40cd`) aus `danwa/tests/` nach `danwa-core/tests/backend/` portiert wurden, sind aktuell mit `@pytest.mark.skip` markiert. Diese Tests testen Verhaltenskontrakte, die bereits durch `danwa-core`-native Tests abgedeckt sind — aber die **Skip-Docstrings** schlagen vor, sie entweder zu reaktivieren (gegen die neue API) oder endgültig zu löschen.

**Entscheidungs-Ziel:** Für jeden der 7 Tests entscheiden — entweder **reaktivieren** (an die danwa-core-API anpassen) oder **löschen** (Coverage ist bereits durch native Tests gedeckt). Beide Optionen beinhalten einen CI-Update.

---

## 2. Inventur

### 2.1 Die 7 geskippten Test-Files

| Datei | LoC | Skip-Reason | API-Differenz | Native Tests in `danwa-core` |
|-------|-----|-------------|----------------|-------------------------------|
| `test_dms_core.py` | ~200 | DMS-Core-API | DMS.delete_project(Path vs Dict), DMS.get_rag_context | `test_dms_core_comprehensive.py` (lokal) |
| `test_dms_database.py` | 0* | (Skip-Marker gesetzt, aber Datei ist leer/oder Patch-Marker fehlt) | DB_PATH-Modul-Alias ist da | `test_dms_database.py` wurde überschrieben |
| `test_dms_metadata_index.py` | ~150 | `metadata_index.DMSDB`-Attribut fehlt | `MetadataIndex` API-Refactoring | _keine direkte native Variante_ |
| `test_dms_rag_pipeline.py` | ~300 | RAG-Pipeline-Return-Shapes | `RAGPipeline.process_file` returnt Dict, portierte Tests erwarten List | _keine direkte native Variante_ |
| `test_dms_document_processor.py` | ~250 | PaddleOCR externe Dependency | `document_processor.process_image` ValueError wenn `ocr_enabled=false` | `test_dms_ocr.py` (nativ) |
| `test_dms_config.py` | 1 Test | `load_dms_config()` mergt YAML | Defaults aus `settings.yaml` überschreiben `DEFAULT_DMS_CONFIG` | _keine native Variante_ |
| `test_rag_pipeline_retrieval.py` | ~500 | RAG-Pipeline + HybridRetriever Constructor | `RAGPipeline(config)` vs neue API | _keine direkte native Variante_ |
| `test_paddleocr_integration.py` | ~600 | PaddleOCR fehlt im CI | require libpaddleocr.so + paddleocr pip | `test_dms_ocr.py` (nativ) |

*test_dms_database.py hat nur die Skip-Marker-Zeile, der Test-Body fehlt (oder ist leer).

### 2.2 Existierende Test-Coverage in `danwa-core`

Bereits laufende Tests, die den DMS-Bereich abdecken (166 Tests in `tests/backend/`):

| Datei | Status | Herkunft |
|-------|--------|----------|
| `test_dms_api.py` (DMS HTTP API) | ✅ läuft | Commit `44c8310` (Phase 0a.1) |
| `test_dms_ocr.py` (OCR-Integration) | ✅ läuft | Commit `44c8310` (Phase 0a.1) |
| `test_dms_multitenant_isolation.py` | ✅ läuft | Commit `44c8310` (Phase 0a.1) |
| `test_dms_chunker.py` (TextChunker) | ✅ läuft | Commit `2cd40cd` (Phase 2, **portiert von danwa**) |
| `test_dms_hybrid_retriever.py` (HybridRetriever) | ✅ läuft | Commit `2cd40cd` (Phase 2, portiert) |
| `test_dms_rag_formatter.py` (RAGContextFormatter) | ✅ läuft | Commit `2cd40cd` (Phase 2, portiert) |
| `test_dms_vector_store.py` (DMSVectorStore) | ✅ läuft | Commit `2cd40cd` (Phase 2, portiert + angepasst) |
| `test_dms_project_manager.py` (ProjectManager) | ✅ läuft | Commit `2cd40cd` (Phase 2, portiert + DB_PATH-Alias) |
| `test_dms_memory.py` (DMSMemory) | ✅ läuft | Commit `2cd40cd` (Phase 2, portiert) |

---

## 3. Entscheidungs-Matrix pro Test

| Test-Datei | Entscheidung | Begründung |
|-----------|-------------|------------|
| `test_dms_core.py` | **LÖSCHEN** | `test_dms_core_comprehensive.py` (nativ) deckt denselben Scope ab. Portierte Variante ist veraltet. |
| `test_dms_database.py` | **LÖSCHEN** | Inhaltlich identisch zur nativen Version; die portierte Version ist nur ein Stub. |
| `test_dms_metadata_index.py` | **REAKTIVIEREN** | Kein nativer Test für MetadataIndex. Anpassung an die danwa-core-`MetadataIndex`-API. |
| `test_dms_rag_pipeline.py` | **REAKTIVIEREN** | Kein nativer Test für RAGPipeline-Klasse. Anpassung an neuen Return-Shape. |
| `test_dms_document_processor.py` | **LÖSCHEN** | `test_dms_ocr.py` (nativ) testet OCR-Integration bereits. PaddleOCR-Dependency ist eine zu hohe CI-Hürde. |
| `test_dms_config.py` | **REAKTIVIEREN** | `test_config_defaults` war ein wichtiger Regressions-Test für die alte API. Neuer Test prüft, dass die Defaults erhalten bleiben (auch nach YAML-Merge). |
| `test_rag_pipeline_retrieval.py` | **REAKTIVIEREN** | HybridRetriever hat keine native Test-Coverage. Anpassung an die neue API. |
| `test_paddleocr_integration.py` | **LÖSCHEN** | PaddleOCR-Dependency ist für CI nicht tragbar. `test_dms_ocr.py` (nativ) deckt den OCR-Pfad ab. |

**Resultat:** 3 reaktivieren, 5 löschen.

---

## 4. Vorgehen

### 4.1 Branch-Strategie

| Repo | Branch | Basis |
|------|--------|-------|
| `danwa-core` | `feat/skip-test-reactivation-2026-06` | `origin/main` (HEAD: `122be87`) |

### 4.2 Reihenfolge (jeder Commit einzeln lauffähig + testbar)

| # | Aktion | Commit-Typ |
|---|--------|------------|
| 1 | `test_dms_document_processor.py` löschen (Duplicate von `test_dms_ocr.py`) | `test(backend): remove obsolete danwa-ported document_processor tests (covered by test_dms_ocr.py)` |
| 2 | `test_paddleocr_integration.py` löschen (PaddleOCR fehlt) | `test(backend): remove obsolete danwa-ported paddleocr tests (PaddleOCR not in CI; covered by test_dms_ocr.py)` |
| 3 | `test_dms_database.py` löschen (leer, Duplicate) | `test(backend): remove obsolete danwa-ported database test stub` |
| 4 | `test_dms_core.py` löschen (von `test_dms_core_comprehensive.py` abgedeckt) | `test(backend): remove obsolete danwa-ported dms_core tests (covered by test_dms_core_comprehensive.py)` |
| 5 | `test_dms_metadata_index.py` reaktivieren | `test(backend): rewrite metadata_index tests against danwa-core API` |
| 6 | `test_dms_rag_pipeline.py` reaktivieren | `test(backend): rewrite rag_pipeline tests against danwa-core return shapes` |
| 7 | `test_rag_pipeline_retrieval.py` reaktivieren | `test(backend): rewrite hybrid_retriever + text_chunker tests against danwa-core API` |
| 8 | `test_dms_config.py::test_config_defaults` reaktivieren | `test(backend): rewrite test_config_defaults to validate default-vs-loaded semantics` |
| 9 | Push Branch + PR | — |

### 4.3 Detail-Plan für die 4 Reaktivierungen

#### Commit 5: `test_dms_metadata_index.py`

**Aktuell:** Patch auf `backend.services.dms.metadata_index.DMSDB` — Attribut fehlt.

**Anpassung:** Den nativen `MetadataIndex`-Klassen inspizieren, den Test auf die echte API umschreiben. Wahrscheinlich nutzt `MetadataIndex` einen `DMSDB`-Konstruktor statt Modul-Alias.

```python
# Vorher (portiert aus danwa):
with patch("backend.services.dms.metadata_index.DMSDB", ...):
    idx = MetadataIndex()

# Nachher (danwa-core API):
@pytest.fixture
def idx(tmp_path):
    db_path = tmp_path / "metadata.db"
    db = DMSDB(db_path=db_path)
    idx = MetadataIndex(db)  # oder wie auch immer die API ist
    yield idx
```

#### Commit 6: `test_dms_rag_pipeline.py`

**Aktuell:** `test_process_file_uses_document_processor` prüft `add.call_args_list` — neue API returnt andere Struktur.

**Anpassung:** Test-Rückgabewerte prüfen statt Mock-Calls:

```python
# Vorher:
assert mock_collection.add.call_args_list == [...]

# Nachher (danwa-core API):
result = pipeline.process_file(file_path, project_id="proj_a")
assert "chunk_ids" in result  # oder was auch immer das neue Format ist
```

#### Commit 7: `test_rag_pipeline_retrieval.py`

**Aktuell:** Tests für `HybridRetriever` + `TextChunker` mit alter API.

**Anpassung:** Inspizieren der nativen `HybridRetriever`-Klasse, neue API nutzen. `TextChunker` (aus Phase 2 portiert) läuft bereits grün — die geskippten `HybridRetriever`-Tests anpassen.

#### Commit 8: `test_dms_config.py::test_config_defaults`

**Aktuell:** Vergleicht `loaded_config == DEFAULT_DMS_CONFIG` — aber danwa-core's `load_dms_config()` mergt YAML.

**Anpassung:** Test schreiben, der die **Default-Erhaltung** validiert — d.h. nach dem Merge müssen alle Default-Keys immer noch in `loaded_config` vorhanden sein und ihre Default-Werte behalten, wenn sie nicht explizit überschrieben werden:

```python
# Nachher:
def test_load_dms_config_preserves_all_defaults():
    config = dms_config.load_dms_config()
    for key, default_value in dms_config.DEFAULT_DMS_CONFIG.items():
        assert key in config, f"Default key '{key}' missing after YAML merge"

def test_load_dms_config_yaml_override():
    """YAML can override defaults but does not remove unspecified keys."""
    # Schreibe tmp config mit nur einem Key, prüfe dass andere Defaults bleiben
```

### 4.4 Risiken und Sonderfälle

| Risiko | Impact | Mitigation |
|--------|--------|------------|
| Native `MetadataIndex` API komplett anders als erwartet | Tests können nicht trivial angepasst werden | Phase 1: einfacher Sanity-Test, dann inkrementell erweitern |
| HybridRetriever refaktoriert komplett | `test_rag_pipeline_retrieval.py` bleibt skip | Behalten als `@pytest.mark.skip` mit aktualisiertem Reason, separater Folgeplan |
| `load_dms_config` ändert sich erneut (laufende Refactoring) | `test_config_defaults`-Logik muss immer wieder angepasst werden | Test schreiben, der beide Verhalten (legacy + current) dokumentiert |
| Native Tests brechen durch API-Änderung | Tests, die gerade grün laufen, könnten rot werden | Vor Reaktivierung: alle 166 Tests lokal grün machen, dann erst reaktivieren |

---

## 5. Commit-Reihenfolge (final)

```
# Phase 1: 5 obsolete Tests löschen
danwa-core: test(backend): remove obsolete danwa-ported document_processor tests
danwa-core: test(backend): remove obsolete danwa-ported paddleocr tests
danwa-core: test(backend): remove obsolete danwa-ported database test stub
danwa-core: test(backend): remove obsolete danwa-ported dms_core tests (covered by test_dms_core_comprehensive.py)
danwa-core: test(backend): remove obsolete danwa-ported dms_document_processor tests (Duplicate)

# Phase 2: 4 Tests reaktivieren
danwa-core: test(backend): rewrite metadata_index tests against danwa-core API
danwa-core: test(backend): rewrite rag_pipeline tests against danwa-core return shapes
danwa-core: test(backend): rewrite hybrid_retriever + text_chunker tests against danwa-core API
danwa-core: test(backend): rewrite test_config_defaults to validate default-vs-loaded semantics

# Phase 3: Push + PR
git push -u origin feat/skip-test-reactivation-2026-06
```

**Total:** 9 Commits.

---

## 6. Verifikationskriterien

| Kriterium | Test |
|-----------|------|
| Alle 7 Test-Files entweder gelöscht oder reaktiviert | `grep -L "pytest.mark.skip" tests/backend/{test_dms_core,test_dms_database,test_dms_metadata_index,test_dms_rag_pipeline,test_dms_document_processor,test_dms_config,test_rag_pipeline_retrieval,test_paddleocr_integration}.py` |
| Reaktivierte Tests grün | `uv run pytest tests/backend/test_dms_metadata_index.py tests/backend/test_dms_rag_pipeline.py tests/backend/test_rag_pipeline_retrieval.py tests/backend/test_dms_config.py -v --tb=short` exit 0 |
| Keine neuen Test-Failures in danwa-core | `uv run pytest tests/backend -q --tb=no` zeigt keine neuen Failures vs. Baseline `122be87` |
| `danwa-core` Build und Imports stabil | `uv run python -c "import backend.core.debate_engine; ..."` läuft |
| `danwa` Working-Tree bleibt clean (cross-repo smoke) | `cd /media/data/coding/danwa && npm run build && uv run pytest tests/backend/test_session_db.py -q` |

---

## 7. Was bewusst NICHT in diesem Plan enthalten ist

- **Coverage-Threshold-Anpassung** in `pyproject.toml` (aktuell 60%, real 37%) — separater Plan
- **`uv.lock`-Cleanup** in beiden Repos — separate Commits
- **Coverage-Erhöhung** durch Hinzufügen neuer Test-Cases — separates Coverage-Improvement
- **Pydantic-Migration** der DMS-Schemas (DMS.delete_project nimmt jetzt vermutlich `Path` statt `Dict`) — separate Architektur-Entscheidung
- **API-Konsolidierung** zwischen danwa und danwa-core DMS-Layer (über `src/` vs `backend/services/dms/`) — separater ADR-Plan
- **HybridRetriever-Refactoring** — falls nötig, separater Architektur-Plan

---

## 8. Zeitplan

```
Phase 1 (Tests löschen):    1 Tag  (~30 min)
  - Löschen + Smoke-Test nach jedem Commit

Phase 2 (Tests reaktivieren): 2-3 Tage  (jeweils ~3-5 Stunden pro Test)
  - API-Discovery
  - Test-Rewrite
  - Lokal pytest grün

Phase 3 (PR):                0.5 Tage

Gesamt: ~4-5 Tage
```

---

## 9. Vorbedingungen

1. ✅ Phase 0a abgeschlossen (Tests aus `danwa` nach `danwa-core` migriert)
2. ✅ Phase 1.2 + 2 abgeschlossen (Source-Module portiert, 26 Tests nach `danwa-core` kopiert)
3. ✅ Branches nach `main` gemergt (HEAD: `122be87`)
4. Vor Beginn: frischer `git fetch`, Working-Tree clean in `danwa-core`
5. Lokale `uv run pytest tests/backend` läuft grün (Baseline verifizieren)
