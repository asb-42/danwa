# Document Management — tests

# Document Management — Tests

The test suite for the Document Management System (DMS) validates every component involved in document ingestion, chunking, vector storage, hybrid retrieval, and RAG context management. Tests are written with `pytest` and make extensive use of `unittest.mock` to isolate units, while a subset of tests (database, document processor) exercise real I/O against temporary files or databases.

## Test Architecture

Each test file maps directly to a source module under `src/dms/`, with two exceptions:

- `test_doc_parser.py` tests the generic `DocumentParser` in `src/tools/doc_parser.py`
- `test_paddleocr_integration.py` validates the OCR branch inside `document_processor.py`

The call graph (extracted from the codebase) shows that the tests cover all public methods of the DMS subsystem, including edge cases like empty results, missing metadata, cascading deletes, and error fallbacks.

```mermaid
graph TD
    TC[test_dms_config]
    TH[test_dms_chunker]
    TD[test_dms_database]
    TP[test_dms_document_processor]
    TR[test_dms_hybrid_retriever]
    TM[test_dms_metadata_index]
    TJ[test_dms_project_manager]
    TF[test_dms_rag_formatter]
    TL[test_dms_rag_pipeline]
    TV[test_dms_vector_store]
    TCORE[test_dms_core & comprehensive]
    TMEM[test_dms_memory]
    TPARSE[test_doc_parser]
    TPADDLE[test_paddleocr_integration]

    subgraph Source Modules (src/dms/)
        C[chunker]
        DB[database]
        DP[document_processor]
        HR[hybrid_retriever]
        MI[metadata_index]
        PM[project_manager]
        RF[rag_context_formatter]
        RP[rag_pipeline]
        VS[vector_store]
        DMS[dms / DMS]
        MEM[dms_memory]
    end
    subgraph Other
        PARSER[src/tools/doc_parser]
    end

    TC -->|loads| DB
    TH --> C
    TD --> DB
    TP --> DP
    TPADDLE --> DP
    TR --> HR
    TM --> MI
    TJ --> PM
    TF --> RF
    TL --> RP
    TV --> VS
    TCORE --> DMS
    TMEM --> MEM
    TPARSE --> PARSER
```

The diagram shows the primary mapping. Redundant edges are omitted for clarity – for example, `test_dms_core` also depends on `DB`, `VS`, `HR`, etc. through the mocked `DMS` class, but those are tested indirectly and are covered by the module's dedicated test files.

## Test Files and Coverage

### Configuration Validation – `test_dms_config.py`

Validates `load_dms_config()`:

- Default values match `DEFAULT_DMS_CONFIG`.
- `chunk_size` must be >0.
- `chunk_overlap` must be < `chunk_size`.
- A missing `dms` section falls back to defaults.

### Chunker – `test_dms_chunker.py`

Exercises `TextChunker.chunk()` with token‑accurate text generation (`_make_text_with_tokens` uses `tiktoken`):

- Empty text returns `[]`.
- Text ≤ chunk size (512 tokens) returns a single chunk.
- Text of 513 tokens produces two chunks with 51‑token overlap.
- Multiple chunks maintain the 10% overlap (≈51 tokens).
- Overlap correctness is verified for the entire chain of chunks.

### Database – `test_dms_database.py`

Full CRUD tests for `DMSDB`:

- Projects: create, get (including nonexistent), list (empty and populated), delete (cascades to documents/chunks).
- Documents: add with full metadata, list (scoped to project, empty), delete (cascades to chunks).
- Chunks: add, list (ordered by `chunk_index`).
- RAG context: add, list (scoped to session), remove (including nonexistent), upsert (duplicate insert yields one row).
- Session DB migration: verifies `project_id` and `document_ids` columns exist in the `sessions` table, and that migration is idempotent.

### Document Processor & OCR – `test_dms_document_processor.py`, `test_paddleocr_integration.py`

Tests for `DocumentProcessor.process_file()`:

- **Text/PDF** – delegates to `DocumentParser.parse_file()`. Metadata fields (`source`, `extension`, `ocr_used`, `pages`, `word_count`, `char_count`) are enriched.
- **Images** (`.png`, etc.) – attempts PaddleOCR; if unavailable or fails, falls back to `DocumentParser`. The OCR branch is tested with a mock PaddleOCR module injected via `sys.modules`.
- **Metadata** – verifies that word and character counts are correctly computed.

### Hybrid Retriever – `test_dms_hybrid_retriever.py`

Tests for `HybridRetriever`:

- Initialization stores the vector store and sets default `rrf_k` (60).
- Empty collection returns empty results.
- `_rrf_combine()` correctly merges BM25 and vector results (higher RRF score for overlapping IDs).
- Cross‑encoder is `None` when `sentence_transformers` is unavailable (tested via `patch.dict`).
- Project‑filtered retrieval uses `MetadataIndex.get_chunks_by_project()` when available, or Chroma's `where` clause otherwise.

### Metadata Index – `test_dms_metadata_index.py`

Tests `MetadataIndex` methods that enrich Chroma results with DB metadata:

- `get_chunks_by_project()` – returns empty for no chunks; with chunks, enriches each with `file_name` and `upload_date` from `DMSDB.get_document()`.
- `get_chunks_by_document()` – returns all chunks for a document, preserving `chunk_index` order.
- `get_chunks_by_date_range()` – filters by the `upload_date` metadata field.

### Project Manager – `test_dms_project_manager.py`

Tests `ProjectManager` CRUD:

- Create, get (including nonexistent), list, update (name, description, both, none), delete.
- Delete cascades to documents and chunks (verified via `db` instance).
- Note: `ProjectManager` does **not** expose `add_document`, `delete_document`, or `list_documents` directly (tested via database layer).

### RAG Context Formatter – `test_dms_rag_formatter.py`

Tests `RAGContextFormatter.format()`:

- Empty list → `""`.
- Single chunk → `"[Document 1 from <file_name>]: <text>\n\n"`.
- Multiple chunks → sequential numbering.
- `max_chars` truncation appends `...`.
- Missing `file_name` → fallback to `"Unknown"`.

### RAG Pipeline – `test_dms_rag_pipeline.py`, `test_rag_pipeline_retrieval.py`

Exercises `RAGPipeline.process_document()` and `process_file()`:

- Chunking, adding to vector store, and storing chunk metadata in DB.
- Returns list of chunk IDs (`doc1_chunk_0`, …).
- Empty text, missing document, chunking errors, vector store errors, and DB errors are all handled gracefully (return `[]` or partially return saved IDs).
- Async `process_file` calls `document_processor.process_file` and then proceeds as `process_document`.

### Vector Store – `test_dms_vector_store.py`

Tests `DMSVectorStore` using a mock Chroma client:

- `add_chunks()` generates correct IDs, documents, and metadatas.
- `search()` converts distances to `relevance_score` (`1 - distance`), supports optional `project_id` filter via `where`.
- Empty collection skips `query()` and returns `[]`.
- `delete_document_chunks()` calls Chroma `delete` with appropriate `where`.
- `count()` returns the collection count.

### DMS Core – `test_dms_core.py`, `test_dms_core_comprehensive.py`

The main orchestrator `DMS` is tested in two complementary files:

- **`test_dms_core.py`** – focuses on individual methods with isolated patches:
  - `__init__` creates all sub‑components (DB, ProjectManager, DocumentProcessor, TextChunker, RAGPipeline, VectorStore, MetadataIndex, HybridRetriever).
  - `create_project`, `list_projects`, `delete_project` delegate to `ProjectManager`.
  - `upload_document` validates file existence, project existence, adds a DB record, and triggers async pipeline processing.
  - `get_rag_context` proxies to `HybridRetriever.retrieve`.
  - `add_to_rag_context`, `remove_from_rag_context`, `list_manual_rag_documents` manage an internal set (`_manual_rag_docs`).
  - `get_manual_rag_context` retrieves chunks for those documents via `MetadataIndex`, respecting `k`.
  - `auto_retrieve_for_topic` formats `get_rag_context` results with source, chunk_index, project_id; gracefully handles missing metadata.

- **`test_dms_core_comprehensive.py`** – provides a full fixture that mocks all eight dependencies, then tests:
  - Project creation (success and error).
  - Document upload (success, missing file, invalid project, DB error).
  - `get_rag_context` (success and retrieval error).
  - Full manual RAG context flow (add, duplicate add, list, get with `k`, remove, and empty context).
  - `auto_retrieve_for_topic` (success, empty results, exception).
  - Document management: delete (success, error), list (with project, without).

### DMSMemory – `test_dms_memory.py`

Tests `DMSMemory`, a thin wrapper around `DMS` for the agent memory interface:

- Can be constructed with a default `DMS` instance or an injected one.
- `get_context` calls `DMS.get_rag_context` and formats using `RAGContextFormatter`.
- `add_document_context` / `remove_document_context` delegate to `DMS` methods.
- Exceptions in `get_context` return `""`.

### Document Parser – `test_doc_parser.py`

Tests the generic `DocumentParser` (not strictly part of DMS but used by it):

- Plain text files are read, cleaned (excessive whitespace collapsed), and returned.
- Metadata includes `source`, `extension`, `char_count`, `word_count`.
- Missing file raises `FileNotFoundError`.
- Text beyond ~26 000 characters is truncated and `truncated=True` is set.
- Unknown extensions are still handled.

## Running the Tests

The full DMS test suite can be executed with:

```bash
pytest tests/ -v
```

For a specific component:

```bash
pytest tests/test_dms_chunker.py -v
```

Note that some tests (e.g., `test_doc_parser.py`, `test_dms_document_processor.py`) require access to the `src/` package – run from the repository root or ensure `PYTHONPATH` is set. The database and processor tests create temporary files in `tmp_path`, leaving no artifacts after execution.

## Key Design Principles

- **Isolation through mocking**: All tests that touch `DMS` or its sub‑components mock every external dependency, making them fast and deterministic.
- **Edge cases first**: Empty collections, nonexistent IDs, missing metadata, and runtime exceptions are first‑class test cases – the code is resilient against failures in the OCR layer, database, or vector store.
- **Token‑accurate chunking**: The chunker tests generate text with known token counts, verifying that the overlap is exactly 10% (≈51 tokens for a 512‑token chunk).
- **Hybrid retrieval validation**: The RRF combination and cross‑encoder reranking are tested with synthetic score arrays; the BM25 retrieval is validated by constructing a small in‑memory corpus.
- **Comprehensive manual RAG**: The ability to manually pin documents to a session’s context is tested end‑to‑end, including duplicate prevention and retrieval limits.