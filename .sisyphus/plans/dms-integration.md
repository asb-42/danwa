# DMS Integration Plan: Document Management System for Danwa

## TL;DR

> **Quick Summary**: Integrate a project-wise Document Management System (DMS) into Danwa with PaddleOCR for scanned documents and a RAG-based interface to supply background context to the multi-agent debate system.
> 
> **Deliverables**: 
> - New `src/dms/` module with project/document/chunk management
> - PaddleOCR integration alongside existing doc_parser.py
> - ChromaDB collections for document RAG (separate from debate precedents)
> - Hybrid RAG interface (auto-retrieve + manual add/remove) in Chainlit UI
> - Project management UI with document upload and RAG context preview
>
> **Estimated Effort**: XL (Large)
> **Parallel Execution**: YES - 6 waves
> **Critical Path**: DMS Core → RAG Pipeline → UI Integration → Chainlit Integration
> **RAG Efficiency**: Database-centric architecture with metadata indexing for optimal retrieval performance

---

## Context

### Original Request
Integrate a Document Management System (DMS) into Danwa that:
1. Manages documents project-wise
2. Integrates PaddleOCR for scanned letters/documents
3. Provides RAG-based interface to pass background info to multi-agent system

### Research Findings

**PaddleOCR (v3.5.0)**:
- Installation: `pip install paddlepaddle paddleocr` (CPU) or `paddlepaddle-gpu` (GPU)
- API: `PaddleOCR(use_doc_orientation_classify=False, device="cpu")`
- Supports: images (png/jpg), PDF multi-page, output with bounding boxes + confidence
- Integration: Run alongside pdfplumber/pypdf for optimal accuracy

**RAG Patterns (2026 Benchmarks)**:
- Chunking: 512 tokens, 10-20% overlap (RecursiveCharacterTextSplitter)
- ChromaDB: PersistentClient with separate collections for documents vs precedents
- Hybrid Search: BM25 + Vector with Reciprocal Rank Fusion
- Re-ranking: CrossEncoderReranker to reduce 30→5 results
- Context Injection: Format with `[Document N from {source}]` format

**Current Integration Points**:
- `chainlit_app.py:140-149`: Document upload entry point
- `chainlit_app.py:151-161`: Context assembly from parsed docs
- `debate_engine.py:102`: Context storage in DebateState
- `memory.py`: Existing ChromaDB for precedents (reuse pattern)

### User Decisions

| Question | Answer | Rationale |
|----------|--------|-----------|
| Project structure | Database-centric with metadata indexing | Most RAG-efficient for supplying info to AI agents |
| RAG Interface | Hybrid (auto-retrieve + manual add/remove) | Best of both worlds |
| PaddleOCR strategy | Run alongside existing parsers | Keep accuracy, add OCR capability |

---

## Work Objectives

### Core Objective
Build a RAG-efficient Document Management System that seamlessly integrates with Danwa's multi-agent debate workflow, enabling project-wise document organization with OCR support and intelligent context injection.

### Concrete Deliverables
- `src/dms/` module with `project_manager.py`, `document_processor.py`, `rag_pipeline.py`, `dms.py`
- Extended database schema: `projects`, `documents`, `document_chunks` tables
- PaddleOCR integration in `document_processor.py` (alongside existing parsers)
- New ChromaDB collection: `document_chunks` for RAG
- Hybrid RAG interface in Chainlit UI (auto + manual document selection)
- Project management dashboard in `src/ui/dms_dashboard.py`
- Integration with `chainlit_app.py` and `debate_engine.py`

### Definition of Done
- [ ] User can create/list/delete projects
- [ ] User can upload documents (PDF, DOCX, ODT, images) to projects
- [ ] PaddleOCR processes image-based documents alongside existing parsers
- [ ] Documents are chunked (512 tokens, 10% overlap) and stored in ChromaDB
- [ ] RAG auto-retrieves relevant chunks based on debate topic
- [ ] User can manually add/remove documents from RAG context
- [ ] Debate engine receives RAG context alongside parsed documents
- [ ] All DMS actions are persisted in SQLite + ChromaDB

### Must Have
- Database-centric project/document management with metadata indexing
- PaddleOCR running alongside (not replacing) existing doc_parser.py
- Hybrid RAG: auto-retrieve from topic + manual document selection
- Separate ChromaDB collection for documents (distinct from `debate_precedents`)
- Integration with existing Chainlit UI and debate engine

### Must NOT Have (Guardrails)
- NO folder-based organization (inefficient for RAG)
- NO replacement of existing doc_parser.py (run PaddleOCR alongside)
- NO blocking UI - all document processing must be async with progress feedback
- NO mixing document chunks with debate precedents in same ChromaDB collection
- NO hardcoded paths - all configurable via `config/settings.yaml`

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: YES (pytest, ruff)
- **Automated tests**: YES (TDD) - Each TODO includes test cases
- **Framework**: pytest + pytest-asyncio

### QA Policy
Every task MUST include agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/dms-task-{N}-{scenario}.{ext}`.

- **Backend/RAG**: Use `pytest` with async support
- **UI Components**: Use Chainlit test client or Playwright
- **OCR Validation**: Test with sample scanned images

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - DMS Core Foundation):
├── Task 1: Database schema for DMS (projects, documents, chunks) [quick]
├── Task 2: DMS config extension in settings.yaml [quick]
├── Task 3: ProjectManager class (CRUD operations) [unspecified-high]
├── Task 4: Extend SessionDB with project/document linkage [quick]
├── Task 5: Create src/dms/ module structure [quick]
└── Task 6: PaddleOCR dependency check + install script [quick]

Wave 2 (After Wave 1 - RAG Pipeline + Document Processing):
├── Task 7: DocumentProcessor with PaddleOCR + existing parsers [deep]
├── Task 8: Chunking strategy (512 tokens, 10% overlap) [unspecified-high]
├── Task 9: ChromaDB collection for document_chunks [unspecified-high]
├── Task 10: RAGPipeline - embed + store document chunks [deep]
├── Task 11: Hybrid retriever (BM25 + Vector + Re-ranking) [deep]
└── Task 12: Document metadata indexing for fast filtering [unspecified-high]

Wave 3 (After Wave 2 - Core DMS API):
├── Task 13: DMS class - high-level API for project/doc management [deep]
├── Task 14: Auto-retrieval based on debate topic [unspecified-high]
├── Task 15: Manual document add/remove for RAG context [unspecified-high]
├── Task 16: RAG context formatter for debate engine [quick]
└── Task 17: DMS integration with existing Memory class pattern [unspecified-high]

Wave 4 (After Wave 3 - UI Components):
├── Task 18: Project management dashboard (Chainlit) [visual-engineering]
├── Task 19: Document upload UI with progress feedback [visual-engineering]
├── Task 20: RAG context preview + manual selection UI [visual-engineering]
├── Task 21: DMS dashboard integration in chainlit_app.py [visual-engineering]
└── Task 22: Project/document selector in main chat UI [visual-engineering]

Wave 5 (After Wave 4 - Integration):
├── Task 23: Extend chainlit_app.py to pass RAG context [deep]
├── Task 24: Modify debate_engine.py to accept RAG context [deep]
├── Task 25: Update document context assembly (chainlit_app.py:151-161) [quick]
├── Task 26: Link sessions to projects in SessionDB [quick]
└── Task 27: Update existing PromptManager for DMS-aware prompts [unspecified-high]

Wave 6 (After Wave 5 - Testing + Documentation):
├── Task 28: TDD tests for DMS core (project, document, rag) [unspecified-high]
├── Task 29: TDD tests for PaddleOCR integration [deep]
├── Task 30: TDD tests for RAG pipeline + hybrid retrieval [deep]
├── Task 31: Integration tests for debate engine + RAG context [deep]
└── Task 32: Update docs/user_manual.md with DMS documentation [writing]

Wave FINAL (After ALL tasks — 4 parallel reviews, then user okay):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay

Critical Path: Task 1 → Task 3 → Task 7 → Task 10 → Task 13 → Task 18 → Task 23 → Task 28 → F1-F4 → user okay
Parallel Speedup: ~75% faster than sequential
Max Concurrent: 6 (Waves 1-2), 5 (Waves 3-5), 4 (Wave 6)

### Dependency Matrix (Abbreviated)

- **1-6**: - - 3, 4, 5, 6
- **7**: 5, 6 - 8, 9, 10
- **8**: 7 - 9, 10
- **9**: 5, 6 - 10, 11
- **10**: 8, 9 - 11, 13
- **11**: 9, 10 - 13, 14
- **12**: 9, 10 - 13, 14
- **13**: 10, 11, 12 - 14, 15, 16
- **14**: 11, 13 - 15, 23
- **15**: 13 - 16, 20, 23
- **16**: 13, 14 - 23, 24
- **17**: 9, 10, 13 - 23
- **18**: 13 - 19, 21
- **19**: 7, 18 - 20, 21
- **20**: 15, 19 - 21, 23
- **21**: 18, 19, 20 - 22, 23
- **22**: 20, 21 - 23
- **23**: 16, 17, 21, 22 - 24, 25, 28
- **24**: 16, 23 - 25, 31
- **25**: 23, 24 - 26, 31
- **26**: 4, 25 - 28
- **27**: 13, 23 - 28
- **28**: 7, 10, 13 - F1-F4
- **29**: 7, 10 - F1-F4
- **30**: 11, 14 - F1-F4
- **31**: 24, 25 - F1-F4
- **32**: 23, 24, 25 - F1-F4

### Agent Dispatch Summary

- **1**: **6** - T1-T6 → `quick`
- **2**: **6** - T7-T12 → `deep`, `unspecified-high`
- **3**: **5** - T13-T17 → `deep`, `unspecified-high`
- **4**: **5** - T18-T22 → `visual-engineering`
- **5**: **5** - T23-T27 → `deep`, `unspecified-high`
- **6**: **5** - T28-T32 → `unspecified-high`, `writing`
- **FINAL**: **4** - T21-T24 → `oracle`, `unspecified-high`, `deep`

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.
> **A task WITHOUT QA Scenarios is INCOMPLETE. No exceptions.**

### Wave 1: DMS Core Foundation

- [x] 1. Database Schema for DMS (projects, documents, chunks)

  **What to do**:
  - Create `src/dms/database.py` with SQLite tables:
    - `projects`: `id`, `name`, `description`, `created_at`, `metadata_json`
    - `documents`: `id`, `project_id`, `filename`, `file_path`, `file_type`, `page_count`, `word_count`, `char_count`, `uploaded_at`, `metadata_json`
    - `document_chunks`: `id`, `document_id`, `chunk_index`, `text`, `embedding_id`, `metadata_json` (page, position)
  - Extend `SessionDB` in `src/core/session_db.py` with:
    - Add `project_id` column to `sessions` table
  - Add `document_ids` column (JSON array) to `sessions` table
  - Create migration function for existing databases
  - Write tests: `tests/test_dms_database.py` with CRUD operations for all tables

  **Must NOT do**:
  - Do NOT create folder-based storage (user chose DB-centric for RAG efficiency)
  - Do NOT mix with existing `debate_precedents` ChromaDB collection

  **Recommended Agent Profile**:
  > Category: `unspecified-high`
  > Reason: Database schema design with migrations requires careful planning
  > Skills: [] (no special skills needed)
  > Skills Evaluated but Omitted: `git-master` (not needed for schema design)

  **Parallelization**:
  - **Can Run In Parallel**: NO (foundation for all other tasks)
  - **Parallel Group**: Wave 1 (with Tasks 2-6)
  - **Blocks**: Tasks 3, 4, 7, 8, 9, 10, 13
  - **Blocked By**: None (can start immediately)

  **References**:
  - `src/core/session_db.py:19-33` - Existing session DB pattern to follow
  - `src/core/memory.py:18-23` - ChromaDB PersistentClient pattern

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_database.py::test_create_project` → PASS
  - [ ] `pytest tests/test_dms_database.py::test_add_document` → PASS
  - [ ] `pytest tests/test_dms_database.py::test_add_chunks` → PASS
  - [ ] SessionDB migration adds `project_id`, `document_ids` columns

  **QA Scenarios**:

  ```
  Scenario: Create project and verify persistence
    Tool: Bash (pytest)
    Preconditions: Clean test database
    Steps:
      1. Run `uv run pytest tests/test_dms_database.py::test_create_project -v`
      2. Verify exit code 0
    Expected Result: Test passes, project retrievable by ID
    Evidence: `.sisyphus/evidence/dms-task-1-project-create.json`
  
  Scenario: SessionDB migration for project linking
    Tool: Bash (pytest)
    Preconditions: Existing sessions table without new columns
    Steps:
      1. Run `uv run pytest tests/test_dms_database.py::test_session_db_migration -v`
      2. Verify columns `project_id`, `document_ids` exist
    Expected Result: Migration successful, columns present
    Evidence: `.sisyphus/evidence/dms-task-1-migration.json`
  ```

  **Commit**: YES | Message: `feat(dms): add database schema for projects, documents, chunks` | Files: `src/dms/database.py`, `src/core/session_db.py`, `tests/test_dms_database.py` | Pre-commit: `uv run pytest tests/test_dms_database.py -v`

- [x] 2. DMS Config Extension in settings.yaml

  **What to do**:
  - Extend `config/settings.yaml` with DMS section:
    ```yaml
    dms:
      enabled: true
      storage_path: "dms_storage"
      chunk_size: 512
      chunk_overlap: 51  # 10%
      embedding_model: "intfloat/multilingual-e5-small"
      ocr_enabled: true
      ocr_device: "cpu"  # or "gpu:0"
      max_file_size_mb: 50
    ```
  - Create `src/dms/config.py` to load DMS settings
  - Write tests: Verify config loading, defaults, validation

  **Must NOT do**:
  - Do NOT hardcode paths - use config
  - Do NOT enable OCR by default (user may not have PaddleOCR installed)

  **Recommended Agent Profile**:
  > Category: `quick`
  > Reason: Simple config file extension, well-defined schema
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4, 5, 6)
  - **Blocks**: Task 8, 13
  - **Blocked By**: None

  **References**:
  - `config/settings.yaml:1-9` - Existing settings structure
  - `src/core/llm_router.py:7-8` - Config loading pattern

  **Acceptance Criteria**:
  - [ ] `uv run pytest tests/test_dms_config.py -v` → PASS
  - [ ] `config/settings.yaml` has `dms:` section

  **QA Scenarios**:

  ```
  Scenario: Load DMS config with defaults
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_config.py::test_config_defaults -v`
    Expected Result: Config loads with correct defaults
    Evidence: `.sisyphus/evidence/dms-task-2-config-defaults.json`
  
  Scenario: Invalid config raises error
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_config.py::test_config_validation -v`
      2. Verify invalid chunk_size raises ValueError
    Expected Result: Proper error message
    Evidence: `.sisyphus/evidence/dms-task-2-config-error.json`
  ```

  **Commit**: YES | Message: `feat(dms): add DMS config to settings.yaml` | Files: `config/settings.yaml`, `src/dms/config.py`, `tests/test_dms_config.py`

- [x] 3. ProjectManager Class (CRUD Operations)

  **What to do**:
  - Create `src/dms/project_manager.py`:
    - `create_project(name, description, metadata)` → returns project dict
    - `list_projects()` → returns list of projects
    - `get_project(project_id)` → returns project or None
    - `update_project(project_id, **kwargs)` → updates fields
    - `delete_project(project_id)` → cascades to documents
  - Use `database.py` for persistence
  - Write tests: `tests/test_dms_project_manager.py`

  **Must NOT do**:
  - Do NOT store files in project-named folders (DB-centric approach)
  - Do NOT delete documents from disk on project delete (configurable retention)

  **Recommended Agent Profile**:
  > Category: `unspecified-high`
  > Reason: Business logic for project management with cascading deletes
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Task 1 schema)
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4, 5, 6)
  - **Blocks**: Task 13, 18
  - **Blocked By**: Task 1

  **References**:
  - `src/core/session_db.py:35-46` - CRUD pattern in SessionDB

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_project_manager.py -v` → PASS (all CRUD tests)
  - [ ] Project deletion cascades to documents (not files on disk)

  **QA Scenarios**:

  ```
  Scenario: Create and retrieve project
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_project_manager.py::test_create_and_get -v`
    Expected Result: Project retrievable after creation
    Evidence: `.sisyphus/evidence/dms-task-3-crud.json`
  
  Scenario: Delete project cascades to documents
    Tool: Bash (pytest)
    Steps:
      1. Create project, add document
      2. Delete project
      3. Verify document removed from DB
    Expected Result: Document deleted from DB, file on disk optionally removed
    Evidence: `.sisyphus/evidence/dms-task-3-cascade.json`
  ```

  **Commit**: YES | Message: `feat(dms): add ProjectManager with CRUD operations` | Files: `src/dms/project_manager.py`, `tests/test_dms_project_manager.py`

- [x] 4. Extend SessionDB with Project/Document Linkage

  **What to do**:
  - Modify `src/core/session_db.py`:
    - Add `project_id TEXT` column to `sessions` table
    - Add `document_ids TEXT` column (JSON array of document IDs)
    - Update `save_session()` to accept `project_id`, `document_ids`
    - Update `list_sessions()` to support `project_id` filter
    - Write migration test: existing DB gets new columns
  - Write tests in `tests/test_session_db.py`

  **Must NOT do**:
  - Do NOT break existing session saving (backward compatible)
  - Do NOT store full document content in sessions table

  **Recommended Agent Profile**:
  > Category: `quick`
  > Reason: Extends existing SessionDB with new columns
  > Skills: [`git-master`] (for checking existing DB migration patterns)

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Task 1 schema)
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 5, 6)
  - **Blocks**: Task 23, 26
  - **Blocked By**: Task 1

  **References**:
  - `src/core/session_db.py:19-33` - Existing table definition
  - `src/core/session_db.py:35-46` - Existing save_session pattern

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_session_db.py::test_save_with_project -v` → PASS
  - [ ] Migration adds columns without data loss

  **QA Scenarios**:

  ```
  Scenario: Save session with project linkage
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_session_db.py::test_save_with_project -v`
    Expected Result: Session saved with project_id and document_ids
    Evidence: `.sisyphus/evidence/dms-task-4-session-link.json`
  
  Scenario: List sessions filtered by project
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_session_db.py::test_list_by_project -v`
    Expected Result: Only sessions from specified project returned
    Evidence: `.sisyphus/evidence/dms-task-4-filter.json`
  ```

  **Commit**: YES | Message: `feat(dms): extend SessionDB with project/document linkage` | Files: `src/core/session_db.py`, `tests/test_session_db.py`

- [x] 5. Create src/dms/ Module Structure

  **What to do**:
  - Create directory `src/dms/` with `__init__.py`
  - Create placeholder files:
    - `database.py` (Task 1)
    - `config.py` (Task 2)
    - `project_manager.py` (Task 3)
    - `document_processor.py` (Task 7)
    - `rag_pipeline.py` (Task 10)
    - `dms.py` (Task 13 - high-level API)
  - Create `tests/test_dms_*.py` files as needed
  - Update `pyproject.toml` if needed for new dependencies

  **Must NOT do**:
  - Do NOT import from files that don't exist yet
  - Do NOT add PaddleOCR dependency to main pyproject.toml (optional extra)

  **Recommended Agent Profile**:
  > Category: `quick`
  > Reason: Directory structure creation, no complex logic
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 4, 6)
  - **Blocks**: Task 7, 8, 10, 13
  - **Blocked By**: None

  **References**:
  - `src/core/__init__.py` - Existing module init pattern

  **Acceptance Criteria**:
  - [ ] `src/dms/__init__.py` exists
  - [ ] All placeholder files created (empty or with basic structure)
  - [ ] `python -c "from src.dms import DMS"` works

  **QA Scenarios**:

  ```
  Scenario: Module imports successfully
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run python -c "from src.dms import DMS; print('OK')"`
    Expected Result: No ImportError
    Evidence: `.sisyphus/evidence/dms-task-5-import.txt`
  ```

  **Commit**: YES | Message: `feat(dms): create src/dms/ module structure` | Files: `src/dms/__init__.py`, `src/dms/*.py`

- [x] 6. PaddleOCR Dependency Check + Install Script

  **What to do**:
  - Update `pyproject.toml` with optional DMS dependency group:
    ```toml
    [project.optional-dependencies]
    dms = ["paddlepaddle>=3.0", "paddleocr>=3.5.0"]
    ```
  - Create `scripts/setup_dms.sh`:
    - Check if PaddleOCR already installed
    - Install CPU version by default: `uv pip install paddlepaddle paddleocr`
    - Offer GPU option: `uv pip install paddlepaddle-gpu paddleocr`
  - Modify `setup.sh` to offer DMS setup option
  - Write test: Verify PaddleOCR imports when installed

  **Must NOT do**:
  - Do NOT install PaddleOCR by default in main setup
  - Do NOT break existing setup.sh

  **Recommended Agent Profile**:
  > Category: `quick`
  > Reason: Shell script + pyproject.toml modification
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 4, 5)
  - **Blocks**: Task 7 (PaddleOCR usage)
  - **Blocked By**: None

  **References**:
  - `pyproject.toml:21-23` - Existing optional-dependencies pattern
  - `setup.sh` - Existing setup script to extend

  **Acceptance Criteria**:
  - [ ] `uv run pip install "danwa[dms]"` installs PaddleOCR
  - [ ] `scripts/setup_dms.sh` is executable and works

  **QA Scenarios**:

  ```
  Scenario: Install DMS dependencies
    Tool: Bash
    Steps:
      1. Run `bash scripts/setup_dms.sh --dry-run`
      2. Verify paddlepaddle and paddleocr in install list
    Expected Result: Dependencies listed correctly
    Evidence: `.sisyphus/evidence/dms-task-6-install.txt`
  
  Scenario: PaddleOCR imports after install
    Tool: Bash
    Steps:
      1. Run `uv run python -c "from paddleocr import PaddleOCR; print('OK')"`
    Expected Result: Import succeeds
    Evidence: `.sisyphus/evidence/dms-task-6-import.txt`
  ```

  **Commit**: YES | Message: `feat(dms): add PaddleOCR dependency and setup script` | Files: `pyproject.toml`, `scripts/setup_dms.sh`

---

### Wave 2: RAG Pipeline + Document Processing (After Wave 1)

- [x] 7. DocumentProcessor with PaddleOCR + Existing Parsers)

  **What to do**:
  - Create `src/dms/document_processor.py`:
    - `process_file(file_path, project_id)` → returns `{text, metadata, chunks}`
    - Integration strategy (run alongside existing parsers):
      ```python
      def process_file(self, file_path):
          ext = Path(file_path).suffix.lower()
          # Images/scans → PaddleOCR
          if ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif']:
              return self._process_with_paddle(file_path)
          # Existing parsers for native formats
          else:
              return self._process_with_existing(file_path)  # Uses doc_parser.py
      ```
    - PaddleOCR initialization (configurable CPU/GPU):
      ```python
      from paddleocr import PaddleOCR
      self.ocr = PaddleOCR(
          use_doc_orientation_classify=False,
          use_doc_unwarping=False,
          device="cpu"  # or "gpu:0" from config
      )
      ```
    - Write tests: `tests/test_dms_document_processor.py`

  **Must NOT do**:
  - Do NOT replace doc_parser.py entirely (user chose "run alongside")
  - Do NOT block UI during processing (use async wrappers)

  **Recommended Agent Profile**:
  > Category: `deep`
  > Reason: Integrates multiple parsing strategies with OCR
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Task 5 module structure)
  - **Parallel Group**: Wave 2 (with Tasks 8-12)
  - **Blocks**: Task 13, 14, 15
  - **Blocked By**: Task 5

  **References**:
  - `src/tools/doc_parser.py:14-68` - Existing parser pattern to wrap
  - PaddleOCR research - API usage from librarian agent

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_document_processor.py -v` → PASS
  - [ ] PaddleOCR processes images, existing parser handles PDF/DOCX

  **QA Scenarios**:

  ```
  Scenario: Process scanned image with PaddleOCR
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_document_processor.py::test_paddle_ocr_image -v`
    Expected Result: Text extracted with bounding boxes
    Evidence: `.sisyphus/evidence/dms-task-7-ocr-image.json`
  
  Scenario: Process PDF with existing parser
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_document_processor.py::test_existing_parser -v`
    Expected Result: Uses doc_parser.py for native PDF
    Evidence: `.sisyphus/evidence/dms-task-7-existing.json`
  ```

  **Commit**: YES | Message: `feat(dms): add DocumentProcessor with PaddleOCR + existing parsers` | Files: `src/dms/document_processor.py`, `tests/test_dms_document_processor.py`

- [x] 8. Chunking Strategy (512 tokens, 10% overlap) [6/6 pass]

  **What to do**:
  - Add chunking to `document_processor.py`:
    - Use `RecursiveCharacterTextSplitter` from langchain (or implement own)
    - 512 tokens target, 51 token overlap (10%)
    - Preserve metadata per chunk: `page`, `position`, `document_id`
  - For PaddleOCR output: chunk by text blocks with bounding box preservation
  - For existing parser output: chunk by character count
  - Write tests: Verify chunk sizes, overlap, metadata

  **Must NOT do**:
  - Do NOT use fixed character count (use token-based for accuracy)
  - Do NOT lose metadata during chunking (page numbers, positions)

  **Recommended Agent Profile**:
  > Category: `unspecified-high`
  > Reason: Token counting + overlap calculation requires precision
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Task 7)
  - **Parallel Group**: Wave 2 (with Tasks 7, 9-12)
  - **Blocks**: Task 10, 11, 13
  - **Blocked By**: Task 7

  **References**:
  - RAG research - Chunking strategies (512 tokens, 10-20% overlap)
  - `src/tools/doc_parser.py` - Text extraction output format

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_document_processor.py::test_chunking -v` → PASS
  - [ ] Chunks have 512±50 tokens, 10% overlap

  **QA Scenarios**:

  ```
  Scenario: Verify chunk sizes and overlap
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_document_processor.py::test_chunk_sizes -v`
    Expected Result: All chunks 460-560 tokens, overlap ~51 tokens
    Evidence: `.sisyphus/evidence/dms-task-8-chunks.json`
  ```

  **Commit**: YES | Message: `feat(dms): implement chunking strategy (512 tokens, 10% overlap)` | Files: `src/dms/document_processor.py`

- [x] 9. ChromaDB Collection for Document Chunks)

  **What to do**:
  - Create `src/dms/vector_store.py`:
    - Initialize separate ChromaDB collection: `document_chunks`
    - Use same PersistentClient as `memory.py` but separate collection
    - Metadata schema per chunk:
      ```python
      {
          "document_id": "doc_abc123",
          "project_id": "proj_xyz",
          "chunk_index": 0,
          "page": 1,
          "source": "report.pdf",
          "total_chunks": 10
      }
      ```
    - Embedding function: Use `intfloat/multilingual-e5-small` (from `custom_embedding.py` or configure new)
    - Methods: `add_chunks(document_id, chunks, metadata)`, `search(query, project_id=None, k=5)`
  - Write tests: `tests/test_dms_vector_store.py`

  **Must NOT do**:
  - Do NOT mix with `debate_precedents` collection
  - Do NOT use default embedding without configuring (multilingual needed for DE content)

  **Recommended Agent Profile**:
  > Category: `unspecified-high`
  > Reason: ChromaDB configuration with metadata filtering
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Task 5)
  - **Parallel Group**: Wave 2 (with Tasks 7, 8, 10-12)
  - **Blocks**: Task 10, 11, 13, 14
  - **Blocked By**: Task 5

  **References**:
  - `src/core/memory.py:18-23` - Existing ChromaDB pattern to follow
  - `src/core/custom_embedding.py` - Existing embedding function

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_vector_store.py -v` → PASS
  - [ ] Collection `document_chunks` separate from `debate_precedents`

  **QA Scenarios**:

  ```
  Scenario: Add and query document chunks
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_vector_store.py::test_add_and_query -v`
    Expected Result: Chunks stored and retrievable by semantic search
    Evidence: `.sisyphus/evidence/dms-task-9-query.json`
  
  Scenario: Filter by project_id
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_vector_store.py::test_project_filter -v`
    Expected Result: Only chunks from specified project returned
    Evidence: `.sisyphus/evidence/dms-task-9-filter.json`
  ```

  **Commit**: YES | Message: `feat(dms): add ChromaDB collection for document chunks` | Files: `src/dms/vector_store.py`, `tests/test_dms_vector_store.py`

- [x] 10. RAGPipeline - Embed + Store Document Chunks) [7/7 pass]

  **What to do**:
  - Create `src/dms/rag_pipeline.py`:
    - `process_and_store(file_path, project_id)` → processes file, chunks, embeds, stores
    - Pipeline: `DocumentProcessor.process_file()` → `chunk()` → `vector_store.add_chunks()`
    - Async support for UI feedback: `async def process_and_store(...)`
    - Progress callback support: `progress_callback(step, detail)`
  - Integrate with `PromptManager` pattern: cache embeddings, hot-reload config
  - Write tests: `tests/test_dms_rag_pipeline.py`

  **Must NOT do**:
  - Do NOT block UI during processing (use async)
  - Do NOT store full document text in ChromaDB (chunked only)

  **Recommended Agent Profile**:
  > Category: `deep`
  > Reason: Multi-step pipeline with async support
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 7, 8, 9)
  - **Parallel Group**: Wave 2 (with Tasks 7-9, 11, 12)
  - **Blocks**: Task 13, 14, 15, 16, 17
  - **Blocked By**: Tasks 7, 8, 9

  **References**:
  - `src/core/debate_engine.py:87-170` - Async pipeline pattern with progress callback
  - RAG research - Production patterns (LangChain, Dify)

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_rag_pipeline.py -v` → PASS
  - [ ] Full pipeline: file → chunks → embeddings → ChromaDB

  **QA Scenarios**:

  ```
  Scenario: Full RAG pipeline execution
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_rag_pipeline.py::test_full_pipeline -v`
    Expected Result: Document processed, chunked, stored in ChromaDB
    Evidence: `.sisyphus/evidence/dms-task-10-pipeline.json`
  
  Scenario: Progress callback called
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_rag_pipeline.py::test_progress -v`
    Expected Result: Progress callback invoked at each step
    Evidence: `.sisyphus/evidence/dms-task-10-progress.json`
  ```

  **Commit**: YES | Message: `feat(dms): implement RAG pipeline (process → chunk → embed → store)` | Files: `src/dms/rag_pipeline.py`, `tests/test_dms_rag_pipeline.py`

- [x] 11. Hybrid Retriever (BM25 + Vector + Re-ranking)) [5/5 pass]

  **What to do**:
  - Extend `rag_pipeline.py` with hybrid retrieval:
    - BM25 retriever for keyword matching (from existing text)
    - Vector retriever for semantic search (ChromaDB)
    - EnsembleRetriever with Reciprocal Rank Fusion (weights: BM25=0.4, Vector=0.6)
    - Optional: CrossEncoderReranker for re-ranking (top 30 → top 5)
  - Methods:
    - `hybrid_search(query, project_id=None, k=5)` → returns ranked chunks
    - `keyword_search(query, project_id)` → BM25 only
    - `semantic_search(query, project_id)` → Vector only
  - Write tests: Verify hybrid results better than individual methods

  **Must NOT do**:
  - Do NOT use only BM25 (loses semantic understanding)
  - Do NOT use only Vector (loses keyword precision)
  - Do NOT re-rank without checking model availability

  **Recommended Agent Profile**:
  > Category: `deep`
  > Reason: Complex retrieval logic with fusion and re-ranking
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Task 10)
  - **Parallel Group**: Wave 2 (with Tasks 7-10, 12)
  - **Blocks**: Task 14, 15, 16, 23
  - **Blocked By**: Task 10

  **References**:
  - RAG research - Hybrid search patterns (open-webui, Quivr)
  - RAG research - Re-ranking with CrossEncoder

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_rag_pipeline.py::test_hybrid_search -v` → PASS
  - [ ] Hybrid results include both keyword and semantic matches

  **QA Scenarios**:

  ```
  Scenario: Hybrid search returns combined results
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_rag_pipeline.py::test_hybrid_search -v`
    Expected Result: Results from both BM25 and Vector retrievers
    Evidence: `.sisyphus/evidence/dms-task-11-hybrid.json`
  
  Scenario: Re-ranking reduces result count
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_rag_pipeline.py::test_reranking -v`
    Expected Result: 30 initial results → 5 after re-ranking
    Evidence: `.sisyphus/evidence/dms-task-11-rerank.json`
  ```

  **Commit**: YES | Message: `feat(dms): add hybrid retriever (BM25 + Vector + Re-ranking)` | Files: `src/dms/rag_pipeline.py`

- [x] 12. Document Metadata Indexing for Fast Filtering) [5/5 pass]

  **What to do**:
  - Create `src/dms/metadata_index.py`:
    - Maintain in-memory index of document metadata for fast filtering
    - Index fields: `project_id`, `document_id`, `source`, `uploaded_at`, `chunk_count`
    - Methods: `update_index(document_id, metadata)`, `filter_documents(project_id=None, **kwargs)`
  - Integrate with SQLite `documents` table (Task 1)
  - Support queries like: "all documents in project X with >5 chunks"
  - Write tests: Verify fast filtering without full table scan

  **Must NOT do**:
  - Do NOT store full chunk text in index (metadata only)
  - Do NOT use linear scan for filtering (use indexed fields)

  **Recommended Agent Profile**:
  > Category: `unspecified-high`
  > Reason: Indexing logic with query optimization
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 1, 9, 10)
  - **Parallel Group**: Wave 2 (with Tasks 7-11)
  - **Blocks**: Task 14, 15, 16
  - **Blocked By**: Tasks 1, 9, 10

  **References**:
  - `src/dms/database.py` (Task 1) - SQLite storage for documents
  - `src/dms/vector_store.py` (Task 9) - ChromaDB for chunks

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_metadata_index.py -v` → PASS
  - [ ] Filter operations complete in <10ms for 1000 documents

  **QA Scenarios**:

  ```
  Scenario: Fast filter by project_id
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_metadata_index.py::test_filter_project -v`
    Expected Result: Only documents from specified project returned in <10ms
    Evidence: `.sisyphus/evidence/dms-task-12-filter.json`
  ```

  **Commit**: YES | Message: `feat(dms): add document metadata indexing for fast filtering` | Files: `src/dms/metadata_index.py`, `tests/test_dms_metadata_index.py`

---

### Wave 3: Core DMS API (After Wave 2)

- [x] 13. DMS Class - High-Level API for Project/Doc Management) [6/6 pass]

  **What to do**:
  - Create `src/dms/dms.py`:
    - `create_project(name, description)` → returns project
    - `upload_document(project_id, file_path)` → processes, chunks, stores
    - `list_documents(project_id=None)` → returns docs with metadata
    - `delete_document(document_id)` → removes from DB + ChromaDB
    - `delete_project(project_id)` → cascades appropriately
  - Integrate all components: ProjectManager, DocumentProcessor, RAGPipeline, VectorStore, MetadataIndex
  - Use `PromptManager` pattern: cache, hot-reload config
  - Write tests: `tests/test_dms_core.py`

  **Must NOT do**:
  - Do NOT expose database internals (clean API only)
  - Do NOT block on upload (async with progress callback)

  **Recommended Agent Profile**:
  > Category: `deep`
  > Reason: High-level orchestration of all DMS components
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 7-12)
  - **Parallel Group**: Wave 3 (with Tasks 14-17)
  - **Blocks**: Tasks 14, 15, 16, 18, 19, 21, 23
  - **Blocked By**: Tasks 7, 8, 9, 10, 11, 12

  **References**:
  - `src/core/debate_engine.py:35-70` - Engine pattern to follow
  - `src/core/prompt_manager.py:11-62` - Manager pattern with cache

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_core.py -v` → PASS
  - [ ] `upload_document()` processes, chunks, stores in ChromaDB

  **QA Scenarios**:

  ```
  Scenario: Upload and retrieve document via DMS
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_core.py::test_upload_and_retrieve -v`
    Expected Result: Document stored, chunks retrievable
    Evidence: `.sisyphus/evidence/dms-task-13-upload.json`
  
  Scenario: Delete project cascades
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_core.py::test_delete_cascade -v`
    Expected Result: Project + docs + chunks removed
    Evidence: `.sisyphus/evidence/dms-task-13-cascade.json`
  ```

  **Commit**: YES | Message: `feat(dms): add DMS class with high-level API` | Files: `src/dms/dms.py`, `tests/test_dms_core.py`

- [x] 14. Auto-Retrieval Based on Debate Topic) [3/3 pass]

  **What to do**:
  - Add to `src/dms/rag_pipeline.py`:
    - `auto_retrieve(topic, project_id=None, k=5)` → returns relevant chunks
    - Uses hybrid search (Task 11) with optional project filter
    - Formats output as context string:
      ```python
      f"[Document {i} from {source} (page {page})]\n{text}"
      ```
    - Applies same formatting as `chainlit_app.py:151-161` for consistency
  - Write tests: Verify auto-retrieved chunks match topic

  **Must NOT do**:
  - Do NOT return raw chunks without formatting
  - Do NOT ignore project_id filter when provided

  **Recommended Agent Profile**:
  > Category: `unspecified-high`
  > Reason: Query formulation + formatting for LLM consumption
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Task 13)
  - **Parallel Group**: Wave 3 (with Tasks 13, 15-17)
  - **Blocks**: Tasks 15, 16, 23, 24
  - **Blocked By**: Tasks 11, 13

  **References**:
  - `src/ui/chainlit_app.py:151-161` - Existing context format
  - RAG research - Context injection patterns

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_rag_pipeline.py::test_auto_retrieve -v` → PASS
  - [ ] Retrieved chunks formatted as `[Document N from X (page Y)]...`

  **QA Scenarios**:

  ```
  Scenario: Auto-retrieve based on topic
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_rag_pipeline.py::test_auto_retrieve -v`
    Expected Result: Top 5 chunks semantically related to topic
    Evidence: `.sisyphus/evidence/dms-task-14-retrieve.json`
  ```

  **Commit**: YES | Message: `feat(dms): add auto-retrieval based on debate topic` | Files: `src/dms/rag_pipeline.py`

- [x] 15. Manual Document Add/Remove for RAG Context) [5/5 pass]

  **What to do**:
  - Add to `src/dms/dms.py`:
    - `add_to_rag_context(document_id, session_id)` → marks doc for RAG
    - `remove_from_rag_context(document_id, session_id)` → unmarks
    - `get_rag_context(session_id)` → returns formatted context string
  - Store mappings in SQLite: `rag_context` table:
      ```sql
      CREATE TABLE rag_context (
          session_id TEXT,
          document_id TEXT,
          added_at TEXT,
          PRIMARY KEY (session_id, document_id)
      )
      ```
  - Write tests: Verify manual add/remove affects RAG context

  **Must NOT do**:
  - Do NOT modify auto-retrieved results (separate manual selection)
  - Do NOT store full document text in `rag_context` table

  **Recommended Agent Profile**:
  > Category: `unspecified-high`
  > Reason: Database operations + RAG context management
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Task 13)
  - **Parallel Group**: Wave 3 (with Tasks 13, 14, 16, 17)
  - **Blocks**: Tasks 20, 23, 24
  - **Blocked By**: Tasks 13, 14

  **References**:
  - `src/core/session_db.py:19-33` - SQLite table pattern
  - User decision: "Hybrid" approach (auto + manual)

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_core.py::test_manual_rag -v` → PASS
  - [ ] Manual docs added/removed affect `get_rag_context()`

  **QA Scenarios**:

  ```
  Scenario: Manual document add to RAG context
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_core.py::test_add_manual_rag -v`
    Expected Result: Document appears in RAG context
    Evidence: `.sisyphus/evidence/dms-task-15-manual.json`
  ```

  **Commit**: YES | Message: `feat(dms): add manual document add/remove for RAG context` | Files: `src/dms/dms.py`, `src/dms/database.py`

- [x] 16. RAG Context Formatter for Debate Engine) [6/6 pass]

  **What to do**:
  - Create `src/dms/context_formatter.py`:
    - `format_context(auto_chunks, manual_chunks)` → combined string
    - Format consistent with `chainlit_app.py:151-161`:
      ```python
      context = f"[Analysierte Dokumente]\n"
      for chunk in all_chunks:
          context += f"### Dokument: {chunk['source']}\n"
          context += f"Metadaten: {json.dumps(chunk['metadata'])}\n"
          context += f"Inhalt:\n{chunk['text']}\n\n"
      ```
    - Deduplicate chunks (same `document_id` + `chunk_index`)
    - Truncate total context to 25k chars (match `doc_parser.py:62-64`)
  - Write tests: Verify formatting matches existing pattern

  **Must NOT do**:
  - Do NOT change existing `[Analysierte Dokumente]` format (UI expects it)
  - Do NOT exceed 25k char limit

  **Recommended Agent Profile**:
  > Category: `unspecified-high`
  > Reason: String formatting with deduplication and truncation
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 14, 15)
  - **Parallel Group**: Wave 3 (with Tasks 13-15, 17)
  - **Blocks**: Tasks 23, 24, 25
  - **Blocked By**: Tasks 13, 14, 15

  **References**:
  - `src/ui/chainlit_app.py:151-161` - Existing context format
  - `src/tools/doc_parser.py:58-64` - Truncation pattern

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_context_formatter.py -v` → PASS
  - [ ] Output format matches `[Analysierte Dokumente]` pattern

  **QA Scenarios**:

  ```
  Scenario: Format matches existing pattern
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_context_formatter.py::test_format_match -v`
    Expected Result: Output starts with `[Analysierte Dokumente]`
    Evidence: `.sisyphus/evidence/dms-task-16-format.json`
  
  Scenario: Truncation at 25k chars
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_context_formatter.py::test_truncation -v`
    Expected Result: Output ≤ 25,000 chars
    Evidence: `.sisyphus/evidence/dms-task-16-truncate.json`
  ```

  **Commit**: YES | Message: `feat(dms): add RAG context formatter for debate engine` | Files: `src/dms/context_formatter.py`, `tests/test_dms_context_formatter.py`

- [x] 17. DMS Integration with Existing Memory Class Pattern) [6/6 pass]

  **What to do**:
  - Create `src/dms/__init__.py` that provides clean imports:
    ```python
    from .dms import DMS
    from .document_processor import DocumentProcessor
    from .rag_pipeline import RAGPipeline
    ```
  - Follow `memory.py` pattern: instantiate in `chainlit_app.py` like `DebateMemory`
  - Add `src/dms/` to Python path (update `pyproject.toml` if needed)
  - Write tests: Verify DMS can be imported and instantiated like Memory

  **Must NOT do**:
  - Do NOT create circular imports (check `src/core/__init__.py`)
  - Do NOT break existing Memory class imports

  **Recommended Agent Profile**:
  > Category: `unspecified-high`
  > Reason: Module integration following existing patterns
  > Skills: [`git-master`] (for import pattern verification)

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 13-16)
  - **Parallel Group**: Wave 3 (with Tasks 13-16)
  - **Blocks**: Tasks 23, 24, 25
  - **Blocked By**: Tasks 13, 14, 15, 16

  **References**:
  - `src/core/memory.py` - Existing Memory class pattern
  - `src/ui/chainlit_app.py:10-12` - Existing import pattern

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_import.py -v` → PASS
  - [ ] DMS can be instantiated in chainlit_app.py

  **QA Scenarios**:

  ```
  Scenario: DMS imports successfully
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_import.py -v`
    Expected Result: All DMS classes importable
    Evidence: `.sisyphus/evidence/dms-task-17-import.json`
  ```

  **Commit**: YES | Message: `feat(dms): integrate DMS with existing Memory class pattern` | Files: `src/dms/__init__.py`, `tests/test_dms_import.py`

---

### Wave 4: UI Components (After Wave 3)

- [x] 18. Project Management Dashboard (Chainlit) [3/3 pass]

  **What to do**:
  - Create `src/ui/dms_dashboard.py`:
    - `render_dms_dashboard(db, page=0, filter_project=None)` → displays projects
    - Shows: project name, description, document count, created date
    - Actions: `dms_create`, `dms_delete`, `dms_view_docs`, `dms_page`
  - Follow `src/ui/dashboard.py` pattern (render_dashboard)
  - Add navigation: pagination, filter by name
  - Write tests: `tests/test_dms_dashboard.py`

  **Must NOT do**:
  - Do NOT create new Chainlit app (integrate with existing)
  - Do NOT block UI during project listing (async with pagination)

  **Recommended Agent Profile**:
  > Category: `visual-engineering`
  > Reason: Chainlit UI components with actions and pagination
  > Skills: [`dev-browser`] (for UI testing)

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Task 13 DMS class)
  - **Parallel Group**: Wave 4 (with Tasks 19-22)
  - **Blocks**: Tasks 21, 23
  - **Blocked By**: Tasks 13, 14, 15, 16, 17

  **References**:
  - `src/ui/dashboard.py:7-40` - Existing dashboard pattern to follow
  - `src/ui/chainlit_app.py:104-117` - Dashboard trigger pattern

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_dashboard.py -v` → PASS
  - [ ] Shows projects with document counts

  **QA Scenarios**:

  ```
  Scenario: Render DMS dashboard
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_dashboard.py::test_render -v`
    Expected Result: Dashboard renders with project list
    Evidence: `.sisyphus/evidence/dms-task-18-dashboard.json`
  
  Scenario: Pagination works
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_dashboard.py::test_pagination -v`
    Expected Result: Page navigation works
    Evidence: `.sisyphus/evidence/dms-task-18-pagination.json`
  ```

  **Commit**: YES | Message: `feat(dms): add DMS project management dashboard` | Files: `src/ui/dms_dashboard.py`, `tests/test_dms_dashboard.py`

- [x] 19. Document Upload UI with Progress Feedback) [4/4 pass]

  **What to do**:
  - Extend `src/ui/chainlit_app.py` with document upload action:
    - `dms_upload` action: opens file picker, calls `dms.upload_document()`
    - Show progress bar during processing (PaddleOCR + chunking)
    - Display result: filename, chunk count, OCR confidence
  - Support batch upload (multiple files)
  - Write tests: `tests/test_dms_upload_ui.py`

  **Must NOT do**:
  - Do NOT block UI during processing (use `cl.Message` for progress)
  - Do NOT use synchronous file operations (use `asyncio.to_thread`)

  **Recommended Agent Profile**:
  > Category: `visual-engineering`
  > Reason: Chainlit file upload + progress feedback
  > Skills: [`dev-browser`]

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Task 18 for DMS integration)
  - **Parallel Group**: Wave 4 (with Tasks 18, 20-22)
  - **Blocks**: Tasks 21, 23
  - **Blocked By**: Tasks 7, 18

  **References**:
  - `src/ui/chainlit_app.py:140-149` - Existing upload pattern
  - `src/ui/chainlit_app.py:163-166` - Progress callback pattern

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_upload_ui.py -v` → PASS
  - [ ] Progress feedback shown during processing

  **QA Scenarios**:

  ```
  Scenario: Upload document with progress
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_upload_ui.py::test_upload_progress -v`
    Expected Result: Progress messages shown during processing
    Evidence: `.sisyphus/evidence/dms-task-19-progress.json`
  ```

  **Commit**: YES | Message: `feat(dms): add document upload UI with progress feedback` | Files: `src/ui/chainlit_app.py`, `tests/test_dms_upload_ui.py`

- [x] 20. RAG Context Preview + Manual Selection UI) [4/4 pass]

  **What to do**:
  - Create `src/ui/rag_context_ui.py`:
    - `render_rag_context(session_id, auto_chunks, manual_docs)` → displays context preview
    - Show: auto-retrieved chunks with similarity scores
    - Manual section: list of project documents with add/remove buttons
    - Preview: formatted context string (truncated to 500 chars)
  - Integrate with `dms.py:get_rag_context()`
  - Write tests: `tests/test_rag_context_ui.py`

  **Must NOT do**:
  - Do NOT auto-add all project documents (user must select manually)
  - Do NOT show full context (truncate for preview)

  **Recommended Agent Profile**:
  > Category: `visual-engineering`
  > Reason: Chainlit UI with action buttons and preview
  > Skills: [`dev-browser`]

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 15, 19)
  - **Parallel Group**: Wave 4 (with Tasks 18, 19, 21, 22)
  - **Blocks**: Tasks 21, 23
  - **Blocked By**: Tasks 15, 19

  **References**:
  - `src/ui/dashboard.py:29-40` - Action buttons pattern
  - User decision: "Hybrid" approach (auto + manual)

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_rag_context_ui.py -v` → PASS
  - [ ] Manual add/remove buttons work

  **QA Scenarios**:

  ```
  Scenario: RAG context preview shows auto chunks
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_rag_context_ui.py::test_auto_preview -v`
    Expected Result: Auto-retrieved chunks displayed with scores
    Evidence: `.sisyphus/evidence/dms-task-20-preview.json`
  
  Scenario: Manual document add/remove
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_rag_context_ui.py::test_manual_toggle -v`
    Expected Result: Add/remove buttons update RAG context
    Evidence: `.sisyphus/evidence/dms-task-20-manual.json`
  ```

  **Commit**: YES | Message: `feat(dms): add RAG context preview + manual selection UI` | Files: `src/ui/rag_context_ui.py`, `tests/test_rag_context_ui.py`

- [x] 21. DMS Dashboard Integration in chainlit_app.py) [3/3 pass]

  **What to do**:
  - Add DMS trigger button in `src/ui/chainlit_app.py:104-117`:
    - `dms_open_dash` action → calls `render_dms_dashboard()`
  - Modify `cl.on_chat_start()` to initialize DMS:
    - `cl.user_session.set("dms", DMS(...))`
  - Follow existing `cl.on_chat_start()` pattern at lines 23-117
  - Write tests: Verify DMS initializes alongside session_db

  **Must NOT do**:
  - Do NOT modify existing dashboard (keep separate)
  - Do NOT break existing `open_dash` action

  **Recommended Agent Profile**:
  > Category: `visual-engineering`
  > Reason: Chainlit action integration with existing UI
  > Skills: [`dev-browser`]

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 18, 19, 20)
  - **Parallel Group**: Wave 4 (with Tasks 18-20, 22)
  - **Blocks**: Tasks 23, 24
  - **Blocked By**: Tasks 18, 19, 20

  **References**:
  - `src/ui/chainlit_app.py:23-117` - Existing `cl.on_chat_start()` pattern
  - `src/ui/chainlit_app.py:104-117` - Dashboard trigger pattern

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_chainlit_app_dms.py -v` → PASS
  - [ ] DMS initializes when chat starts

  **QA Scenarios**:

  ```
  Scenario: DMS dashboard accessible from chat
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_chainlit_app_dms.py::test_dms_trigger -v`
    Expected Result: `dms_open_dash` action triggers dashboard
    Evidence: `.sisyphus/evidence/dms-task-21-trigger.json`
  ```

  **Commit**: YES | Message: `feat(dms): integrate DMS dashboard in chainlit_app.py` | Files: `src/ui/chainlit_app.py`, `tests/test_chainlit_app_dms.py`

- [x] 22. Project/Document Selector in Main Chat UI) [3/3 pass]

  **What to do**:
  - Add to `src/ui/chainlit_app.py:66-101` (ChatSettings):
    - `project_selector`: Dropdown of user's projects
    - `document_filter`: Optional filter by document name/type
    - When project selected: auto-populate RAG context from that project
  - Show selected project/documents in chat header
  - Write tests: Verify selector updates RAG context

  **Must NOT do**:
  - Do NOT auto-select project (user must choose)
  - Do NOT reload all settings when project changes (use callback)

  **Recommended Agent Profile**:
  > Category: `visual-engineering`
  > Reason: Chainlit settings extension with dropdowns
  > Skills: [`dev-browser`]

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 20, 21)
  - **Parallel Group**: Wave 4 (with Tasks 18-21)
  - **Blocks**: Tasks 23, 24, 25
  - **Blocked By**: Tasks 20, 21

  **References**:
  - `src/ui/chainlit_app.py:66-101` - Existing ChatSettings pattern
  - `src/ui/chainlit_app.py:151-161` - Context assembly pattern

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_chainlit_app_dms.py::test_project_selector -v` → PASS
  - [ ] Selecting project updates RAG context

  **QA Scenarios**:

  ```
  Scenario: Project selector in chat settings
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_chainlit_app_dms.py::test_project_select -v`
    Expected Result: Dropdown shows user projects
    Evidence: `.sisyphus/evidence/dms-task-22-selector.json`
  ```

  **Commit**: YES | Message: `feat(dms): add project/document selector in main chat UI` | Files: `src/ui/chainlit_app.py`, `tests/test_chainlit_app_dms.py`

---

### Wave 5: Integration with Existing System (After Wave 4)

- [x] 23. Extend chainlit_app.py to Pass RAG Context) [6/6 pass]

  **What to do**:
  - Modify `src/ui/chainlit_app.py:169-171`:
    - Initialize DMS: `dms = cl.user_session.get("dms") or DMS()`
    - Get RAG context: `rag_context = dms.get_rag_context(state.session_id)`
    - Combine: `full_context = context + "\n\n" + rag_context`
  - Update `engine.run(full_context, ...)` call
  - Handle errors gracefully (DMS unavailable → fallback to original context)
  - Write tests: `tests/test_chainlit_app_dms.py`

  **Must NOT do**:
  - Do NOT break existing document upload flow (140-149)
  - Do NOT require DMS for debate (graceful fallback)

  **Recommended Agent Profile**:
  > Category: `deep`
  > Reason: Modifies core chat flow with RAG integration
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 15, 16, 21, 22)
  - **Parallel Group**: Wave 5 (with Tasks 24-27)
  - **Blocks**: Tasks 24, 25, 28+
  - **Blocked By**: Tasks 15, 16, 21, 22

  **References**:
  - `src/ui/chainlit_app.py:140-171` - Existing upload + context assembly
  - `src/core/debate_engine.py:102` - Context storage in DebateState

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_chainlit_app_dms.py::test_rag_context_passed -v` → PASS
  - [ ] Debate receives RAG context alongside parsed documents

  **QA Scenarios**:

  ```
  Scenario: RAG context passed to debate engine
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_chainlit_app_dms.py::test_rag_passed -v`
    Expected Result: engine.run() receives combined context
    Evidence: `.sisyphus/evidence/dms-task-23-rag-passed.json`
  
  Scenario: Fallback when DMS unavailable
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_chainlit_app_dms.py::test_fallback -v`
    Expected Result: Original context used when DMS fails
    Evidence: `.sisyphus/evidence/dms-task-23-fallback.json`
  ```

  **Commit**: YES | Message: `feat(dms): extend chainlit_app.py to pass RAG context` | Files: `src/ui/chainlit_app.py`

- [x] 24. Modify DebateEngine to Accept RAG Context) [4/4 pass]

  **What to do**:
  - Modify `src/core/debate_engine.py:102`:
    - Accept optional `rag_context` parameter in `run()` method
    - Prepend to `self.state.context` if provided
    - Update docstring to document RAG context injection
  - Ensure RAG context appears BEFORE debate rounds (not after)
  - Write tests: `tests/test_debate_engine_dms.py`

  **Must NOT do**:
  - Do NOT modify existing context assembly (keep `chainlit_app.py:151-161`)
  - Do NOT break existing `engine.run(context)` calls (backward compatible)

  **Recommended Agent Profile**:
  > Category: `deep`
  > Reason: Modifies core engine with RAG integration
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Task 23)
  - **Parallel Group**: Wave 5 (with Tasks 23, 25-27)
  - **Blocks**: Tasks 25, 28+
  - **Blocked By**: Tasks 16, 23

  **References**:
  - `src/core/debate_engine.py:87-170` - Existing `run()` method
  - Task 16 - RAG context formatter pattern

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_debate_engine_dms.py -v` → PASS
  - [ ] RAG context prepended to `state.context`

  **QA Scenarios**:

  ```
  Scenario: DebateEngine accepts RAG context
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_debate_engine_dms.py::test_rag_accepted -v`
    Expected Result: RAG context in state.context
    Evidence: `.sisyphus/evidence/dms-task-24-accepted.json`
  ```

  **Commit**: YES | Message: `feat(dms): modify DebateEngine to accept RAG context` | Files: `src/core/debate_engine.py`

- [x] 25. Update Document Context Assembly (chainlit_app.py:151-161)) [7/7 pass]

  **What to do**:
  - Modify `src/ui/chainlit_app.py:151-161`:
    - Add section: `[RAG Hintergrundinformationen]` between parsed docs and engine call
    - Format: `### RAG Kontext:\n{rag_context}`
    - Deduplicate: Remove overlap between parsed docs and RAG chunks
  - Keep existing `[Analysierte Dokumente]` section intact
  - Write tests: Verify context assembly order

  **Must NOT do**:
  - Do NOT remove existing document parsing (140-149)
  - Do NOT change `[Analysierte Dokumente]` format (UI expects it)

  **Recommended Agent Profile**:
  > Category: `unspecified-high`
  > Reason: String assembly with deduplication logic
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Task 24)
  - **Parallel Group**: Wave 5 (with Tasks 23-24, 26-27)
  - **Blocks**: Tasks 26, 28+
  - **Blocked By**: Tasks 23, 24

  **References**:
  - `src/ui/chainlit_app.py:151-161` - Existing context assembly
  - Task 16 - RAG context formatter

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_chainlit_app_dms.py::test_context_order -v` → PASS
  - [ ] Output: `[Analysierte Dokumente]...\n[RAG Hintergrundinformationen]...`

  **QA Scenarios**:

  ```
  Scenario: Context assembly order correct
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_chainlit_app_dms.py::test_context_order -v`
    Expected Result: Parsed docs BEFORE RAG context
    Evidence: `.sisyphus/evidence/dms-task-25-order.json`
  ```

  **Commit**: YES | Message: `feat(dms): update document context assembly for RAG` | Files: `src/ui/chainlit_app.py`

- [x] 26. Link Sessions to Projects in SessionDB) [12/12 pass]

  **What to do**:
  - Modify `src/ui/chainlit_app.py:227`:
    - Pass `project_id` from UI selector to `db.save_session()`
    - Pass `document_ids` from RAG context to `db.save_session()`
  - Update `src/core/session_db.py:35-46` to accept new fields
  - Write tests: Verify session linked to project + documents

  **Must NOT do**:
  - Do NOT break existing session saving (backward compatible)
  - Do NOT store full document text in sessions table

  **Recommended Agent Profile**:
  > Category: `unspecified-high`
  > Reason: Extends existing session persistence
  > Skills: [`git-master`]

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 4, 23, 25)
  - **Parallel Group**: Wave 5 (with Tasks 23-25, 27)
  - **Blocks**: Tasks 28+
  - **Blocked By**: Tasks 4, 23, 25

  **References**:
  - `src/core/session_db.py:35-46` - Existing save_session pattern
  - Task 4 - SessionDB extension

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_session_db.py::test_session_project_link -v` → PASS
  - [ ] Session retrievable by project_id

  **QA Scenarios**:

  ```
  Scenario: Session linked to project
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_session_db.py::test_project_link -v`
    Expected Result: Session saved with project_id + document_ids
    Evidence: `.sisyphus/evidence/dms-task-26-link.json`
  ```

  **Commit**: YES | Message: `feat(dms): link sessions to projects in SessionDB` | Files: `src/core/session_db.py`, `src/ui/chainlit_app.py`

- [x] 27. Update PromptManager for DMS-Aware Prompts) [4/4 pass]

  **What to do**:
  - Create `config/prompts/dms_context.md`:
    - Prompt variant that includes RAG context instructions
  - Add to `config/prompt_variants.yaml` as `dms` variant
  - Modify `src/core/prompt_manager.py` to support DMS prompt selection
  - Logic: If RAG context present → use `dms` variant
  - Write tests: Verify DMS-aware prompt selection

  **Must NOT do**:
  - Do NOT modify existing prompt variants (A, B)
  - Do NOT hardcode DMS prompts (use PromptManager)

  **Recommended Agent Profile**:
  > Category: `unspecified-high`
  > Reason: Prompt management with conditional selection
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 23-26)
  - **Parallel Group**: Wave 5 (with Tasks 23-26)
  - **Blocks**: Tasks 28+
  - **Blocked By**: Tasks 13, 23-26

  **References**:
  - `src/core/prompt_manager.py:10-62` - Existing variant management
  - `config/prompt_variants.yaml` - Existing variant config

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_prompt_manager_dms.py -v` → PASS
  - [ ] DMS variant selected when RAG context present

  **QA Scenarios**:

  ```
  Scenario: DMS-aware prompt selection
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_prompt_manager_dms.py::test_dms_variant -v`
    Expected Result: `dms` variant selected with RAG context
    Evidence: `.sisyphus/evidence/dms-task-27-prompt.json`
  ```

  **Commit**: YES | Message: `feat(dms): update PromptManager for DMS-aware prompts` | Files: `config/prompts/dms_context.md`, `config/prompt_variants.yaml`, `src/core/prompt_manager.py`

---

### Wave 6: Testing + Documentation (After Wave 5)

- [x] 28. TDD Tests for DMS Core (Project, Document, RAG)) [9/9 pass])

  **What to do**:
  - Create `tests/test_dms_core.py`:
    - Test project CRUD (create, list, delete)
    - Test document upload + chunking
    - Test RAG retrieval (auto + manual)
    - Test DMS integration with SessionDB
  - Create `tests/test_dms_rag.py`:
    - Test hybrid search (BM25 + Vector)
    - Test re-ranking reduces result count
    - Test context formatting matches `[Analysierte Dokumente]` pattern
  - Use TDD: Write tests FIRST, then verify implementation passes

  **Must NOT do**:
  - Do NOT mix with existing test files (keep separate)
  - Do NOT skip TDD cycle (tests first!)

  **Recommended Agent Profile**:
  > Category: `unspecified-high`
  > Reason: Comprehensive test suite for all DMS components
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 7-27)
  - **Parallel Group**: Wave 6 (with Tasks 29-32)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 1-27 (all implementation)

  **References**:
  - `tests/test_debate_engine.py` - Existing test patterns
  - Task 28 - DMS core tests

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_core.py -v` → PASS (all DMS tests)
  - [ ] `pytest tests/test_dms_rag.py -v` → PASS (all RAG tests)

  **QA Scenarios**:

  ```
  Scenario: DMS core tests pass
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_core.py -v`
    Expected Result: All tests PASS
    Evidence: `.sisyphus/evidence/dms-task-28-core.json`
  
  Scenario: RAG pipeline tests pass
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_rag.py -v`
    Expected Result: All tests PASS
    Evidence: `.sisyphus/evidence/dms-task-28-rag.json`
  ```

  **Commit**: YES | Message: `test(dms): add TDD test suite for DMS core + RAG` | Files: `tests/test_dms_core.py`, `tests/test_dms_rag.py`

- [x] 29. TDD Tests for PaddleOCR Integration) [4/4 pass]

  **What to do**:
  - Create `tests/test_dms_paddleocr.py`:
    - Test OCR processes images (png, jpg, tiff)
    - Test OCR runs alongside existing parsers (pdfplumber, pypdf, docx)
    - Test PaddleOCR not required (graceful fallback)
    - Test progress callback during OCR processing
  - Mock PaddleOCR imports for environments without it

  **Must NOT do**:
  - Do NOT require PaddleOCR for all tests (mock if unavailable)
  - Do NOT test command-line usage (API only)

  **Recommended Agent Profile**:
  > Category: `deep`
  > Reason: OCR integration with mocking for unavailable environments
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Task 7)
  - **Parallel Group**: Wave 6 (with Tasks 28, 30-32)
  - **Blocks**: F1-F4
  - **Blocked By**: Task 7, 28+

  **References**:
  - PaddleOCR research - API patterns
  - Task 7 - DocumentProcessor integration

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_paddleocr.py -v` → PASS
  - [ ] OCR and existing parsers both work

  **QA Scenarios**:

  ```
  Scenario: PaddleOCR processes image
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_paddleocr.py::test_ocr_image -v`
    Expected Result: Text extracted with confidence scores
    Evidence: `.sisyphus/evidence/dms-task-29-ocr.json`
  
  Scenario: Graceful fallback without PaddleOCR
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_paddleocr.py::test_fallback -v`
    Expected Result: Uses existing parser when OCR unavailable
    Evidence: `.sisyphus/evidence/dms-task-29-fallback.json`
  ```

  **Commit**: YES | Message: `test(dms): add TDD tests for PaddleOCR integration` | Files: `tests/test_dms_paddleocr.py`

- [x] 30. TDD Tests for RAG Pipeline + Hybrid Retrieval) [11/11 pass]

  **What to do**:
  - Extend `tests/test_dms_rag.py`:
    - Test hybrid search (BM25 + Vector) beats individual methods
    - Test re-ranking with CrossEncoder reduces 30→5 results
    - Test metadata filtering by project_id
    - Test context injection format matches chainlit_app.py:151-161
    - Test auto-retrieve based on debate topic

  **Must NOT do**:
  - Do NOT use only BM25 or only Vector (must test hybrid)
  - Do NOT skip re-ranking tests (important for quality)

  **Recommended Agent Profile**:
  > Category: `deep`
  > Reason: Complex retrieval logic with fusion and re-ranking
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 10, 11, 14)
  - **Parallel Group**: Wave 6 (with Tasks 28, 29, 31, 32)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 10, 11, 14, 28+

  **References**:
  - RAG research - Hybrid search patterns
  - Task 11 - Hybrid retriever implementation

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_rag.py -v` → PASS
  - [ ] Hybrid search returns better results than individual methods

  **QA Scenarios**:

  ```
  Scenario: Hybrid search beats individual methods
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_rag.py::test_hybrid_beats_individual -v`
    Expected Result: Hybrid returns more relevant results
    Evidence: `.sisyphus/evidence/dms-task-30-hybrid.json`
  
  Scenario: Re-ranking reduces count
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_rag.py::test_rerank_reduces -v`
    Expected Result: 30 initial → 5 after re-ranking
    Evidence: `.sisyphus/evidence/dms-task-30-rerank.json`
  ```

  **Commit**: YES | Message: `test(dms): add TDD tests for RAG pipeline + hybrid retrieval` | Files: `tests/test_dms_rag.py`

- [x] 31. Integration Tests for Debate Engine + RAG Context) [11/11 pass]

  **What to do**:
  - Create `tests/test_dms_integration.py`:
    - Test debate engine receives RAG context alongside parsed docs
    - Test `chainlit_app.py` assembles context correctly:
      `[Analysierte Dokumente]...[RAG Hintergrundinformationen]...`
    - Test session saved with project_id + document_ids
    - Test DMS dashboard renders in Chainlit UI
    - Mock DMS to test graceful fallback when unavailable

  **Must NOT do**:
  - Do NOT require DMS for debate (graceful fallback to original context)
  - Do NOT modify existing debate tests (add new ones)

  **Recommended Agent Profile**:
  > Category: `deep`
  > Reason: Multi-component integration testing
  > Skills: [`dev-browser`] (for UI tests)

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 23-27)
  - **Parallel Group**: Wave 6 (with Tasks 28-30, 32)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 23-27, 28+

  **References**:
  - `src/ui/chainlit_app.py:140-171` - Context assembly flow
  - Task 23-27 - Integration points

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_dms_integration.py -v` → PASS
  - [ ] Debate receives RAG context correctly

  **QA Scenarios**:

  ```
  Scenario: Debate engine receives RAG context
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_integration.py::test_rag_to_debate -v`
    Expected Result: engine.run() receives combined context
    Evidence: `.sisyphus/evidence/dms-task-31-rag.json`
  
  Scenario: Graceful fallback without DMS
    Tool: Bash (pytest)
    Steps:
      1. Run `uv run pytest tests/test_dms_integration.py::test_fallback -v`
    Expected Result: Original context used when DMS fails
    Evidence: `.sisyphus/evidence/dms-task-31-fallback.json`
  ```

  **Commit**: YES | Message: `test(dms): add integration tests for debate engine + RAG context` | Files: `tests/test_dms_integration.py`

- [x] 32. Update docs/user_manual.md with DMS Documentation) [docs updated]

  **What to do**:
  - Append DMS section to `docs/user_manual.md`:
    - "Document Management System (DMS)" chapter
    - Subsections: Project Management, Document Upload, PaddleOCR, RAG Context
    - Update table of contents
    - Add DMS architecture diagram (text-based)
    - Document new UI elements: project selector, RAG preview
    - Update README.md with DMS feature highlight

  **Must NOT do**:
  - Do NOT create separate DMS manual (integrate into existing)
  - Do NOT write unnecessary comments/docstrings (code should be self-documenting)

  **Recommended Agent Profile**:
  > Category: `writing`
  > Reason: Documentation writing in English
  > Skills: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Tasks 1-31)
  - **Parallel Group**: Wave 6 (with Tasks 28-31)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 1-31 (all implementation + tests)

  **References**:
  - `docs/user_manual.md` - Existing documentation to extend
  - `README.md` - Existing project README

  **Acceptance Criteria**:
  - [ ] `docs/user_manual.md` has DMS section (≥500 lines added)
  - [ ] README.md mentions DMS feature

  **QA Scenarios**:

  ```
  Scenario: DMS section added to manual
    Tool: Bash
    Steps:
      1. Check `docs/user_manual.md` contains "Document Management System"
      2. Verify ≥500 lines added
    Expected Result: DMS documented comprehensively
    Evidence: `.sisyphus/evidence/dms-task-32-manual.txt`
  
  Scenario: README mentions DMS
    Tool: Bash
    Steps:
      1. Check `README.md` contains "DMS" or "Document Management"
    Expected Result: Feature highlighted in README
    Evidence: `.sisyphus/evidence/dms-task-32-readme.txt`
  ```

  **Commit**: YES | Message: `docs(dms): update user manual with DMS documentation` | Files: `docs/user_manual.md`, `README.md`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.

- [x] F1. Plan Compliance Audit — `oracle` [3/32 tasks have issues]
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. Code Quality Review — `unspecified-high`
  Run `uv run ruff check src/dms/ tests/test_dms*.py`. Run `uv run pytest tests/ -v`. Review all changed files for: `as any`/`@ts-ignore`, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp).   
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. Real Manual QA — `unspecified-high` (+ `playwright` skill if UI) [PARTIAL - backend verified, UI blocked by subagent misconfiguration]
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (DMS + debate engine works together, not isolation). Test edge cases: empty state, invalid input, rapid actions. Save to `.sisyphus/evidence/final-qa/`.   
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. Scope Fidelity Check — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.   
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **1**: `feat(dms): add database schema for projects, documents, chunks` — `src/dms/database.py`, `src/core/session_db.py`, `tests/test_dms_database.py`
- **2**: `feat(dms): add DMS config to settings.yaml` — `config/settings.yaml`, `src/dms/config.py`, `tests/test_dms_config.py`
- **3**: `feat(dms): add ProjectManager with CRUD operations` — `src/dms/project_manager.py`, `tests/test_dms_project_manager.py`
- **4**: `feat(dms): extend SessionDB with project/document linkage` — `src/core/session_db.py`, `tests/test_session_db.py`
- **5**: `feat(dms): create src/dms/ module structure` — `src/dms/*.py`
- **6**: `feat(dms): add PaddleOCR dependency and setup script` — `pyproject.toml`, `scripts/setup_dms.sh`
- **7**: `feat(dms): add DocumentProcessor with PaddleOCR + existing parsers` — `src/dms/document_processor.py`, `tests/test_dms_document_processor.py`
- **8**: `feat(dms): implement chunking strategy (512 tokens, 10% overlap)` — `src/dms/document_processor.py`
- **9**: `feat(dms): add ChromaDB collection for document chunks` — `src/dms/vector_store.py`, `tests/test_dms_vector_store.py`
- **10**: `feat(dms): implement RAG pipeline (process → chunk → embed → store)` — `src/dms/rag_pipeline.py`, `tests/test_dms_rag_pipeline.py`
- **11**: `feat(dms): add hybrid retriever (BM25 + Vector + Re-ranking)` — `src/dms/rag_pipeline.py`
- **12**: `feat(dms): add document metadata indexing for fast filtering` — `src/dms/metadata_index.py`, `tests/test_dms_metadata_index.py`
- **13**: `feat(dms): add DMS class with high-level API` — `src/dms/dms.py`, `tests/test_dms_core.py`
- **14**: `feat(dms): add auto-retrieval based on debate topic` — `src/dms/rag_pipeline.py`
- **15**: `feat(dms): add manual document add/remove for RAG context` — `src/dms/dms.py`, `src/dms/database.py`
- **16**: `feat(dms): add RAG context formatter for debate engine` — `src/dms/context_formatter.py`, `tests/test_dms_context_formatter.py`
- **17**: `feat(dms): integrate DMS with existing Memory class pattern` — `src/dms/__init__.py`, `tests/test_dms_import.py`
- **18**: `feat(dms): add DMS project management dashboard` — `src/ui/dms_dashboard.py`, `tests/test_dms_dashboard.py`
- **19**: `feat(dms): add document upload UI with progress feedback` — `src/ui/chainlit_app.py`, `tests/test_dms_upload_ui.py`
- **20**: `feat(dms): add RAG context preview + manual selection UI` — `src/ui/rag_context_ui.py`, `tests/test_rag_context_ui.py`
- **21**: `feat(dms): integrate DMS dashboard in chainlit_app.py` — `src/ui/chainlit_app.py`
- **22**: `feat(dms): add project/document selector in main chat UI` — `src/ui/chainlit_app.py`
- **23**: `feat(dms): extend chainlit_app.py to pass RAG context` — `src/ui/chainlit_app.py`
- **24**: `feat(dms): modify DebateEngine to accept RAG context` — `src/core/debate_engine.py`, `tests/test_debate_engine_dms.py`
- **25**: `feat(dms): update document context assembly for RAG` — `src/ui/chainlit_app.py`
- **26**: `feat(dms): link sessions to projects in SessionDB` — `src/core/session_db.py`
- **27**: `feat(dms): update PromptManager for DMS-aware prompts` — `src/core/prompt_manager.py`, `config/prompts/dms_context.md`
- **28**: `test(dms): add TDD tests for DMS core (project, document, rag)` — `tests/test_dms_core.py`, `tests/test_dms_rag.py`
- **29**: `test(dms): add TDD tests for PaddleOCR integration` — `tests/test_dms_paddleocr.py`
- **30**: `test(dms): add TDD tests for RAG pipeline + hybrid retrieval` — `tests/test_dms_rag.py`
- **31**: `test(dms): add integration tests for debate engine + RAG context` — `tests/test_dms_integration.py`
- **32**: `docs(dms): update user manual with DMS documentation` — `docs/user_manual.md`, `README.md`

---

## Success Criteria

### Verification Commands
```bash
uv run ruff check src/dms/ tests/test_dms*.py
uv run pytest tests/ -v
uv run python -c "from src.dms import DMS; print('DMS module loaded')"
uv run chainlit run src/ui/chainlit_app.py --port 7860  # Manual verification
```

### Final Checklist
- [ ] All "Must Have" present: Database-centric DMS, PaddleOCR alongside existing parsers, Hybrid RAG, Separate ChromaDB collection
- [ ] All "Must NOT Have" absent: Folder-based org, Replaced doc_parser.py, Blocking UI, Mixed collections, Hardcoded paths
- [ ] All tests pass: `uv run pytest tests/ -v` → 0 failures
- [ ] DMS module imports successfully: `from src.dms import DMS`
- [ ] Chainlit app starts with DMS integration
- [ ] User can create project, upload document, get RAG context in debate

