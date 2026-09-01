# Deep-Dive Code Review — Danwa Multi-Repo Stack

**Date:** 2026-08-31
**Reviewer:** Principal Staff Engineer
**Scope:** `danwa` (2603763, 08-04), `danwa-core` (e430b63, 08-03), `danwa-studio` (59a798b, 07-29), `danwa-modules` (56b7b1a, 07-30) — one `git pull --ff-only` per repo before review; all four were already up to date.
**Focus:** (1) inter-repo interconnections, (2) root cause of "agents could not read files stored in the DMS via RAG".

---

## 1. Executive Summary

The stack's interfaces are, at the wiring level, mostly coherent: the frontend auto-resolves tenant/case context and prefers case-scoped endpoints; the backend has a single `deps.py` resolution layer; and the DMS layer shows real multi-tenant discipline (tuple cache keys, project-scoped Chroma filters, foreign-document rejection, dedicated isolation tests). The four-repo split is workable and danwa-studio's proxying to `:8000` is conventional.

But the review found **one systemic defect that fully explains the recurring "agents cannot read DMS files via RAG" complaint — a project-ID split-brain between the case-scoped DMS router and the debate/workflow RAG path** — empirically reproduced below with the production classes and ChromaDB 1.5.9. Four further defects each independently produce the same user-visible symptom (document text invisible to agents or to the UI), which is why the complaint felt intermittent and unfalsifiable: depending on which route uploaded a document and which route reads it, retrieval silently succeeds or silently returns nothing.

Inter-repo hygiene needs attention but is not the source of the RAG failures: the real findings there are a **full duplicated legacy backend committed inside the `danwa` frontend repo**, a **vendored, drifted copy of danwa-modules committed inside danwa-core**, and configuration coupling via a cross-repo `.env` symlink and sibling-directory `manage.sh` assumptions.

**Severity summary: 2 Critical, 6 High, several Medium.** All findings are grounded in code read during this session; line numbers are approximate to file state at the pulled HEADs.

| # | Sev | Issue |
|---|-----|-------|
| 2.1 | **Critical** | RAG split-brain: case-scoped uploads tag chunks `case:{t}:{c}`; debate/workflow RAG filters by raw case UUID → 0 chunks for every tenant-flow case |
| 2.2 | **Critical** | Upload handler blocks the event loop up to 300 s (OCR/PDF parse awaited via `future.result()` in an `async def` route) |
| 2.3 | **High** | 25 000-char truncation at ingestion — large documents lose most content before chunking, silently |
| 2.4 | **High** | Scanned PDFs never OCR'd (OCR only triggers on image extensions) |
| 2.5 | **High** | Frontend "RAG preview" calls `/dms/rag/preview` — route exists in no backend router → guaranteed 404 |
| 2.6 | **High** | Case-scoped `GET /dms/documents/{id}` returns metadata only; the document viewer built on `text_content` shows nothing |
| 2.7 | **High** | No authentication on any DMS endpoint (legacy or case-scoped) |
| 2.8 | **High** | Same physical case DMS opened by multiple cached instances with different bindings; shared SQLite connections used from many threads → logical races, lost RAG selections, duplicated Chroma clients |
| 3.x | Medium | Architectural debt: duplicated legacy backend, drifted vendored modules, two divergent `DMS` classes (one broken), mixed cache keys, `rag_context.session_id` misnomer, swallow-and-return-empty error culture, never-invalidated negative cache |

---

## 2. Critical & High Severity Issues

### 2.1 [CRITICAL] Project-ID split-brain: case-scoped documents are invisible to every agent

**Location**
- Write side: `danwa-core/backend/api/routers/case_scoped.py`, `_get_dms_for_case()` (≈L687–747): binds the DMS with `scope_id = f"case:{tenant_id}:{case_id}"`; every chunk is tagged `project_id = "case:{t}:{c}"` in Chroma (`vector_store.py:add_chunks`) and in `dms.db` (`documents.project_id`).
- Read side: `danwa-core/backend/services/debate/debate_rag.py`, `resolve_rag_context()` (≈L67+) → `get_dms_for_project(project_id)` — called with the **raw case UUID** from:
  - `backend/services/debate_workflow.py:331`
  - `backend/api/routers/workflow_exec.py:394` and `:616`
  - `backend/api/routers/input_composer.py:649`
  - `backend/api/routers/case_scoped.py:1119` (`project_id = case_id` when delegating case-scoped workflow starts)

**Problem.** The same physical case DMS (same `data/tenants/{t}/cases/{c}/dms/` directory: one `dms.db`, one `chroma_db`) is opened under **two different `project_id` bindings**:

- the case-scoped router's synthetic `case:{t}:{c}`, and
- the raw case UUID used by the debate/workflow RAG path.

Every retrieval primitive is hard-scoped by `project_id`: `vector_store.search(where={"project_id": …})`, `metadata_index.get_chunks_by_project`, and — crucially — `metadata_index.get_chunks_by_document`, which **also** filters by project. So both retrieval modes fail:

- auto-retrieve (`auto_retrieve_for_topic`) → hybrid retriever filters by raw UUID → matches nothing;
- explicit document selection (`document_ids` in a debate) → `get_chunks_by_document` filters by raw UUID → matches nothing.

**Empirical reproduction** (production classes, real ChromaDB 1.5.9, this session):

```text
chunks in chroma: 1
A auto-retrieve (scope_id case:t1:c1): 1   ← case-scoped router binding
B auto-retrieve (raw uuid c1-uuid-123): 0  ← debate/workflow RAG binding
B get_chunks_by_document(doc):           0  ← explicit document_ids path
A get_chunks_by_document(doc):           1
```

**Impact.** For any case created through the tenant/case flow, agents (debates, workflows, interactive agent worker) receive **zero document context** even though the documents are listed, analyzed, and "in RAG" in the UI. This is the root cause of the recurring complaint. The bug is silent because every layer swallows errors and returns empty lists (§3.6), and no test covers the router→debate seam: `test_dms_multitenant_isolation.py` writes and reads through the *same* binding, and `test_get_dms_for_project_uses_string_key` even blesses the mixed-type cache (§3.4).

> **Post-review correction (2026-09-01):** A regression suite pinning this exact
> contract does exist — `tests/rag_regression/` (including
> `test_rag_scope_id_regression.py` and migration `v024_rag_project_id_dedup`)
> — but it is **not in pyproject `testpaths`** (`["tests/backend"]`), so it never
> runs in the default suite, and v024 was not wired into `main.py`. The fix
> (danwa-core `ed314a9`) completes that intended contract: bare `case_id`
> binding everywhere, factory case-dir fallback for CaseStore cases, v024
> wired into lifespan (+ `rag_context.session_id` rewrite), and the pinned
> source-contract tests in `test_workspace_list_documents.py` /
> `test_mvp_debate_passes_dms_project_id.py` now pass.

The same seam corrupts **manual RAG state**: `add_to_rag_context` reached via the legacy route (`POST /api/v1/dms/documents/{id}/rag` with `X-Case-Id` → raw UUID instance) persists `rag_context(session_id=raw_uuid, …)`, while the case-scoped instance loads selections for `session_id="case:{t}:{c}"` — so documents toggled via one route don't appear in the other, and debate RAG resolution never sees either binding's data consistently.

**Fix.** Two directions; choose one and enforce it at a single chokepoint:

- **Option A (smallest safe change): normalize to the synthetic scope everywhere.** Do it once, inside the resolution boundary, not at each call site:

  ```python
  # danwa-core/backend/services/dms/service.py

  def get_dms_for_project(project_id: str, project_store: Any = None) -> DMS:
      """Get or create a DMS instance for a project or case.

      Raw case UUIDs are normalized to the canonical case scope id
      ('case:{tenant}:{case}') so that uploads (case-scoped router) and
      retrievals (debates, workflows, input composer) share one binding.
      """
      project_id = _normalize_case_scope(project_id)
      ...
  ```

  with, in the same module (or `backend/api/deps.py` where `get_case_dir` lives):

  ```python
  def _normalize_case_scope(project_id: str) -> str:
      if project_id.startswith("case:"):
          return project_id
      if project_id in ("", "_default"):
          return project_id
      try:
          from backend.api.deps import get_case_dir
          case_dir = get_case_dir(project_id)          # data/tenants/{t}/cases/{c}
          parts = case_dir.parts
          tenant_id = parts[parts.index("tenants") + 1]
          return f"case:{tenant_id}:{project_id}"
      except Exception:
          return project_id                            # legacy project id: unchanged
  ```

  `get_case_dir` already resolves raw case UUIDs via its tenant-directory scan and caches the result, so the normalization is one dict lookup after the first call. `_get_dms_for_case` in the router should then call the same helper for its `scope_id` construction instead of formatting the string inline — one source of truth for the format.

- **Option B (recommended long-term): drop the synthetic namespace.** Case ids are UUIDs; isolation comes from per-case directories, not from the tag string. Binding `project_id = case_id` everywhere removes a whole class of drift bugs, shrinks cache keys to one type, and makes `rag_context.session_id` semantically honest. Requires a one-time backfill.

- **One-time data migration (either option).** Existing installations have mixed tags. Write a migration script that, for every `data/tenants/*/cases/*/dms/`:
  1. rewrites `documents.project_id` (SQLite) to the canonical form;
  2. rewrites the Chroma metadata in lockstep — `collection.get(include=["metadatas"])`, patch each chunk's `project_id`, `collection.update(ids=…, metadatas=…)`. Chunk ids are `f"{document_id}_chunk_{idx}"`, so the SQLite `documents.id` (8-char uuid prefix) is the join key;
  3. rewrites `rag_context.session_id` to the canonical form.

**Verification once fixed:** a regression test that uploads through `POST /tenants/{t}/cases/{c}/dms/documents` and asserts `resolve_rag_context(project_id=case_uuid, document_ids=[doc_id])` returns the chunk. That test fails today — it is the missing seam test.

### 2.2 [CRITICAL] Upload blocks the event loop for up to 300 s

**Location:** `danwa-core/backend/services/dms/service.py`, `DMS.upload_document()` (≈L131–186); routes `dms.py:96` (`upload_document`) and `case_scoped.py` `upload_case_document` (≈L776).

**Problem.** Inside an `async def` route, ingestion runs `asyncio.run(self.rag_pipeline.process_file(...))` in a brand-new `ThreadPoolExecutor` and then **synchronously waits**:

```python
with concurrent.futures.ThreadPoolExecutor() as pool:
    future = pool.submit(asyncio.run, self.rag_pipeline.process_file(doc_id, file_path))
    proc_result = future.result(timeout=300)   # blocks the request thread
```

The route is `async def` but never awaits: the entire OCR/PDF-parse (PaddleOCR/EasyOCR/Tesseract, pdfplumber — CPU-bound, potentially minutes on first run while models download) runs while the event loop's request thread is pinned. Every concurrent SSE debate stream, chat session, and poll stalls for the full duration; several uploads at once stack. The 5-minute ceiling means a slow OCR upload can freeze the whole app for everyone — and because OCR init is synchronous in `__init__` (`_initialize_ocr_sync`), the first image upload after boot also constructs PaddleOCR inline.

**Fix.** Offload properly and bound the work; simplest correct form:

```python
# service.py — module scope: reuse one bounded pool
_INGEST_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="dms-ingest"
)

class DMS:
    async def upload_document_async(self, project_id: str, file_path: str,
                                    original_filename: str = "") -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        # _ingest_blocking: sync wrapper around rag_pipeline.process_file
        proc_result = await loop.run_in_executor(
            _INGEST_POOL, self._ingest_blocking, doc_id, file_path
        )
        ...
```

with `upload_document` delegating to it, and both routes awaiting `await dms.add_document_async(...)`. The product-better option: return `202 Accepted` + `doc_id` immediately after the DB row insert and finish ingestion as a `BackgroundTask`; the UI already shows document rows (with `word_count == 0` as "processing") and the analysis flow tolerates late-arriving text.

### 2.3 [HIGH] 25 000-char truncation at ingestion silently destroys large documents

**Location:** `danwa-core/backend/services/doc_parser.py` — `MAX_CONTEXT_CHARS = 25000`, applied in `_parse_sync()`.

**Problem.** Every document is truncated **before chunking** to its first 25 000 characters:

```python
if len(text) > MAX_CONTEXT_CHARS:
    text = text[:MAX_CONTEXT_CHARS] + "\n\n⚠️ [Document truncated. Context length exceeded.]"
```

A 100-page contract (~300 k chars) enters RAG with under 10 % of its content. Agents then truthfully report that clauses beyond that point are "not in the DMS" — indistinguishable, to a user, from the split-brain symptom (§2.1). Nothing surfaces the truncation: the parse metadata (`metadata["truncated"] = True`) is dropped on the floor — `add_document` writes `metadata_json=""` — and the only trace is a sentinel string buried in the last indexed chunk. The chunker exists precisely to handle long text; truncating pre-chunk defeats it. Protecting *prompt* size is the retrieval formatter's job (`RAGContextFormatter.format(..., max_chars=…)`), not ingestion's.

**Fix.**

```python
# doc_parser.py
MAX_CONTEXT_CHARS = 2_000_000   # ~500 pages; chunking + retrieval caps handle the rest
```

and propagate the truncation flag into the stored document so the UI can show it:

```python
# rag_pipeline.py — after process_file
self.db.update_document_metadata(
    doc_id,
    word_count=proc_result["metadata"].get("word_count", 0),
    # add a `metadata_json` write here with {"truncated": bool(proc_result["metadata"].get("truncated"))}
)
```

### 2.4 [HIGH] Scanned PDFs are never OCR'd

**Location:** `danwa-core/backend/services/dms/document_processor.py` — `process_file()` routes only `IMAGE_EXTENSIONS` to OCR.

**Problem.** A scanned PDF (pages are images, no text layer) goes to `DocumentParser`, `pdfplumber` extracts `""` per page, `rag_pipeline.process_file` logs "No text extracted" and returns zero chunks — the document sits in the DMS listing but contributes nothing to RAG, analysis, or the viewer. For a document-management product whose default OCR language is `deu+eng`, scanned PDFs are surely a common input. Two secondary issues in the same file:
- PaddleOCR is constructed with hardcoded `lang="en"` (in `_try_init_paddleocr`) while config carries `ocr_lang: "deu+eng"` — German documents get English-only OCR whenever Paddle wins the fallback chain. The configured language is only honored by tesseract/easyocr.
- When no OCR engine is available and the file is an image, `_process_with_ocr` "falls back to text extraction" — reading binary image bytes as text — instead of raising; the upload then "succeeds" with garbage or empty text. (The `ocr_enabled=False` path correctly raises `ValueError`.)

**Fix.** Route empty-text PDFs through OCR, and honor `ocr_lang` for Paddle:

```python
# document_processor.py
async def process_file(self, file_path: str) -> dict[str, Any]:
    ext = Path(file_path).suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        if not self.config.get("ocr_enabled", False):
            raise ValueError(...)            # existing, correct behavior
        return await self._process_with_ocr(file_path)
    result = await self._process_with_existing(file_path)
    if ext == ".pdf" and not result["text"].strip() and self.config.get("ocr_enabled", False):
        return await self._process_pdf_with_ocr(file_path)   # rasterize pages (e.g. pdfplumber page.to_image()) → OCR each
    return result
```

```python
# _try_init_paddleocr — honor configured language
ocr = paddle_ocr(
    use_angle_cls=True,
    lang=self.config.get("ocr_paddle_lang", "de"),   # or map ocr_lang; 'en' is wrong for a deu+eng product
    ...
)
```

### 2.5 [HIGH] Frontend "RAG preview" calls a route that exists in no backend → guaranteed 404

**Location:** `danwa/frontend/src/lib/api/document.js:145–156` (`getRagPreview` → `GET /api/v1/tenants/{t}/cases/{c}/dms/rag/preview`, fallback `GET /api/v1/dms/rag/preview`); consumed at `DocumentsView.svelte:340`.

**Problem.** `rg "rag/preview"` across the whole backend returns nothing — neither the legacy `dms.py` router nor `case_scoped.py` defines it. The preview panel in the Documents view therefore *always* 404s and shows "Failed to fetch RAG preview". Any user who tries the one UI affordance that shows "what the agent will see" gets a broken feature, which directly feeds the "RAG doesn't work" perception.

**Fix.** Implement it in the case-scoped router (mirroring what a debate will actually receive), using the normalized scope so the preview is split-brain-proof:

```python
# case_scoped.py
@router.get("/tenants/{tenant_id}/cases/{case_id}/dms/rag/preview")
def preview_case_rag(
    tenant_id: str,
    case_id: str,
    query: str = Query(default=""),
    document_ids: str = Query(default=""),
    include_analysis: bool = Query(default=True),
    case_store: CaseStore = Depends(get_case_store),
):
    """Preview the RAG context exactly as a debate would receive it."""
    from backend.services.debate.debate_rag import resolve_rag_context

    dms = _get_dms_for_case(tenant_id, case_id, case_store)
    ids = [d for d in document_ids.split(",") if d] or None
    rag_context, doc_count = resolve_rag_context(
        project_id=dms._project_id,          # canonical scope id — see §2.1
        case_text=query,
        document_ids=ids,
        rag_auto_retrieve=bool(query),
        include_document_analysis=include_analysis,
    )
    return {"rag_context": rag_context, "document_count": doc_count}
```

Also add the legacy twin (`/api/v1/dms/rag/preview`) since the frontend falls back to it, or remove the fallback.

### 2.6 [HIGH] Case-scoped document endpoint returns metadata only — the viewer shows nothing

**Location:** `danwa-core/backend/api/routers/case_scoped.py` — `get_case_document` (≈L760) calls `dms.get_document(document_id)`; legacy twin `dms.py:63` calls `dms.get_document_content(document_id)`.

**Problem.** `DocumentsView.svelte:1075+` renders `viewingDocContent.text_content`; the case-scoped route returns only the DB row (no chunks joined). Via the tenant/case flow — the primary flow — the document viewer's text panel is always empty. This is *literally* "cannot read the file in the DMS" as experienced by the user, independent of RAG. The docstring ("with its content for viewing") documents the intent; the implementation diverges from the legacy route it replaced.

**Fix.**

```python
@router.get("/tenants/{tenant_id}/cases/{case_id}/dms/documents/{document_id}")
def get_case_document(
    tenant_id: str,
    case_id: str,
    document_id: str,
    case_store: CaseStore = Depends(get_case_store),
):
    """Get a single document with its content for viewing."""
    dms = _get_dms_for_case(tenant_id, case_id, case_store)
    doc = dms.get_document_content(document_id)     # ← metadata + text_content + in_rag
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc
```

While there: the frontend's `updateDocumentText` and `moveDocument` fall back to the legacy `/api/v1/dms/.../text` and `/move` routes ("No tenant-scoped equivalent yet") — the case-scoped router should grow both routes (or the frontend should keep using them knowingly, but then they must work, which they currently do only under the §2.1 fix since they resolve via `get_dms_for_project(raw case_id)`).

### 2.7 [HIGH] DMS endpoints have no authentication

**Location:** `backend/api/routers/dms.py` (all 15 routes), `backend/api/routers/case_scoped.py` (all routes). `rg` for `get_current_user|verify_token` in both files: zero hits. Routers that *do* authenticate: `tenants.py`, `projects.py`, `graph.py`, `inbox.py`, `user_keys.py`, `optimization_proposals.py` (via `backend.api.deps.get_current_user`).

**Problem.** Anyone who can reach the API can list, read, upload to, modify, and delete documents in **any tenant's case** by guessing UUIDs — the entire multi-tenant isolation layer (tuple cache keys, scope filters, foreign-document rejection) trusts the `tenant_id` path parameter and `X-Case-Id` header, which are attacker-controlled when there is no authn. Document contents are the product's most sensitive data. `main.py` carefully disables auth entirely when `jwt_secret_key` is empty — but these routes never had it.

**Fix.** Add the same dependency the tenants router uses, plus a membership check binding the authenticated user to the path tenant:

```python
# case_scoped.py
from backend.api.deps import get_current_user, get_membership_store

@router.post("/tenants/{tenant_id}/cases/{case_id}/dms/documents")
async def upload_case_document(
    tenant_id: str,
    case_id: str,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    case_store: CaseStore = Depends(get_case_store),
):
    _require_case_access(user, tenant_id)   # membership lookup, as in tenants.py routes
    ...
```

Apply to every route in both DMS routers (and audit the rest of `case_scoped.py`: debates and audit endpoints share the same gap). If agents/workers call these APIs internally, give them a service identity rather than leaving the routes open.

### 2.8 [HIGH] One case DMS, multiple cached instances, shared SQLite from many threads

**Location:** `service.py` `_dms_cache` + `_dms_cache_lock`; `database.py` `DMSDB.__init__` (`sqlite3.connect(..., check_same_thread=False)`); `agent_worker.py:_get_document_chunks` (its own cache insertion mirroring `_get_dms_for_case`); `move_document_to` (raw `conn.executemany`).

**Problem.** Three overlapping hazards:

1. **Duplicate bindings.** After the §2.1 split-brain, the *same physical directory* is opened as two cached DMS instances (`case:{t}:{c}` and raw UUID) — two SQLite connections to one `dms.db` (WAL, so no corruption, but see 3) and two Chroma clients to one collection.
2. **Cross-thread connection sharing.** Cached DMS instances are singletons used by any request thread (FastAPI threadpool), the ingest thread (§2.2), and the agent worker — all on one `sqlite3` connection with `check_same_thread=False`. Python 3.11's `sqlite3.threadsafety == 3` makes this memory-safe, but *not* logically safe: multi-statement sequences interleave. Concretely: `rag_pipeline.process_document` commits **per chunk** in a loop; a concurrent `delete_document` (chunks + doc + commit, with rollback-on-error) can interleave between those commits, leaving orphaned chunk rows or a deleted document whose chunks were re-added mid-loop. `update_document_text`'s delete-then-reindex sequence has the same window.
3. **Manual-RAG state duplication.** `_manual_rag_docs` is an in-memory set per instance, hydrated once at init from `rag_context` and mutated on both instances independently — selections made via one route are invisible to the other instance's `list_manual_rag_documents` until restart.

**Fix.** One instance per case, one binding per case (§2.1 removes the duplicate), and serialize DB access per DMS:

```python
# service.py — DMS.__init__
self._db_lock = threading.RLock()

# database.py — simplest robust option: serialize at the DMSDB boundary
class DMSDB:
    def __init__(...):
        ...
        self._lock = threading.RLock()

    def execute(self, sql, params=()):          # route ALL statements through this
        with self._lock:
            return self.conn.execute(sql, params)

    def commit(self):
        with self._lock:
            self.conn.commit()
```

…and wrap `process_document`'s chunk-insert loop in a single transaction (one `commit()` at the end) so a delete can't interleave mid-ingestion. Alternatively replace the hand-rolled `DMSDB` with SQLModel/SQLAlchemy pool — but the lock + single-transaction fixes are 30 lines and remove the hazard class.

> **Remediation status (2026-09-01, danwa-core `6f7d67a`):** §2.3–§2.8 are
> implemented. **§2.3** — `doc_parser.MAX_CONTEXT_CHARS` raised to 2M chars
> (ingestion-side sanity ceiling; prompts stay bounded at chunking/retrieval),
> and `RAGPipeline.process_file` now persists `word_count`/`char_count`/
> `page_count`/`ocr_used` plus `metadata_json={"truncated": …}` via the
> extended `update_document_metadata`; upload responses surface `truncated`.
> **§2.4** — empty-text PDFs are rasterized page-by-page (pdfplumber,
> `ocr_pdf_resolution`, capped by `ocr_pdf_max_pages`) and OCRed per page;
> PaddleOCR lang codes map from `ocr_lang` (`deu→german`, `eng→en`,
> `ocr_paddle_lang` override); a no-engine image/PDF raises `ValueError` → 422
> instead of the binary-as-text fallback, and per-engine handlers propagate
> failures. **§2.5** — case-scoped `GET …/dms/rag/preview` and legacy
> `GET /dms/rag/preview` added, matching `getRagPreview` exactly. **§2.6** —
> `get_case_document` returns `get_document_content` (text + chunk metadata),
> with case-scoped `PUT …/text` and `POST …/move` twins; the frontend prefers
> the tenant-scoped routes. **§2.7** — every DMS route (legacy + case-scoped)
> requires `get_current_user`; tenant-scoped routes enforce membership via
> `_check_tenant_access` (admin bypass, fail-closed 403). **§2.8** — `DMSDB`
> statements serialized through RLock wrappers (`execute`/`executemany`/
> `commit`/`rollback`/`close`), all callers migrated, chunk ingestion batched via
> `add_chunk(commit=False)` + one commit, and `_get_dms_for_case` now caches
> under both the tuple and bare `case_id` keys so `get_dms_for_project` and
> the agent worker reuse the same instance — one case, one DMS, one connection.
> Verified against a pristine HEAD worktree: identical failure sets across all
> affected suites (DMS, OCR, workspace, interactive, auth, multi-tenant,
> migrations); new routes smoke-tested live (401 with auth on, contract-shaped
> 200 with auth off).

---

## 3. Architectural & Design Improvements

### 3.1 Delete the duplicated legacy backend from the `danwa` repo

> **Remediation status (2026-09-02, danwa `main`):** **Done.** Deleted from the
> danwa repo: `backend/` (237 files), `src/` (36), `tests/backend/` (139 — all
> already skip-guarded), `tests/rag_regression/` (byte-identical twins of
> danwa-core's), `docs/api/` (146 pdoc files) + `docs/api-reference.{md,json}`
> (dead-backend OpenAPI output), `Dockerfile.backend`, the backend+celery
> services from `docker-compose.yml`, and all backend-oriented scripts from
> `scripts/` (migrations, seeds, doc/export twins — kept only `libdanwa.sh`,
> a runtime dependency of `manage.sh`). Follow-ups in the same pass:
> `repo-templates/danwa/manage.sh` no longer runs `uvicorn backend.main:app`
> — backend lifecycle delegates to the danwa-core sibling (mock mode stays
> local so BATS `start be` keeps writing `backend.pid` in test sandboxes);
> `doc-api`/`doc-pdoc`/`doc-update`/`test` delegate or point at danwa-core;
> `adr-check` watches `frontend/src` instead of `backend/` dirs; CI/deploy
> workflows, `Makefile`, `pyproject.toml` (deps trimmed to the pytest/ruff
> tooling stack, `testpaths` → `tests/frontend, tests/scripts`), README,
> INSTALL, and the DOX chain were updated. `tests/frontend/test_version_consistency.py`
> was ported from the removed backend suite (keeps the `/version` ↔
> `frontend/package.json` pin; backend-side checks live in danwa-core).
> Verified: `uv run pytest tests/` green (same pre-existing AgentNode layout
> failure as before), full BATS suite green except the pre-existing
> `setup_studio` "node not available" env failure (fails on pristine HEAD
> too), ruff clean. The `.env` → danwa-core symlink was deliberately left
> (§3.7, not approved this session).
`danwa/backend/` is a full copy of the danwa-core backend (**91 files differ** from `danwa-core/backend`), plus a duplicated `src/` core. `danwa/backend/main.py` itself says it is deprecated, "superseded by danwa-core … Do NOT start — shares port 8000", and `danwa/manage.sh` delegates backend lifecycle to `../danwa-core/manage.sh`. Yet the dead tree ships with every frontend commit: it confuses greps (every symbol appears twice), doubles review surface, and invites accidental edits to the wrong copy (this session had to check danwa-core equivalents for every prior-session finding). **Recommendation:** delete `danwa/backend/` and `danwa/src/` (or move to a `legacy/` branch/tag for archaeology), keep only `frontend/`, `docs/`, `plans/`, scripts that genuinely belong to the app repo. This is the single highest-value hygiene change across the four repos.

### 3.2 Un-vendor danwa-modules; treat it as a build input, not a fork

`danwa-core/modules/` is a committed snapshot of danwa-modules inside the danwa-core git repo, and it has drifted: 11 top-level entries vs 22 in the canonical repo; `agent-prompt-modifiers`, `interactive-action-templates`, `schemas/`, `scripts/`, `index.json`, `releases/` are absent from the vendored copy; danwa-core has `lang-de`, `pm-…`, `prompt-modifiers` the canonical repo lacks; and the shared categories (`agent-cores`, `agent-bundles`, `llm-profiles`, `workflows`, …) differ in content. `deploy_import.py` imports from `ROOT/modules` at startup — so what runs in danwa-core is the stale copy, and there is no mechanism updating it. Meanwhile `scripts/import_from_repo.py` already knows how to pull from a registry URL. **Recommendation:** remove `danwa-core/modules/` from git; import modules via the existing `import_from_repo.py` (registry URL, pinned per release) or a git submodule, and record the modules checksum in the release. The `cleanup_legacy.py` mapping (`profiles/* → modules/*`) suggests the vendoring was a transitional crutch — it's time to retire it.

### 3.3 Remove the broken second `DMS` class and `DMSMemory`

> **Remediation status (2026-09-02, danwa-core `main`):** **Done.** Deleted
> `backend/services/dms/dms.py` and `backend/services/dms/dms_memory.py`, plus
> their dead-suite companions `tests/backend/test_dms_memory.py` and the
> 100%-skip-marked `tests/backend/test_dms_core.py`; pruned the dead-class
> test groups from `test_dms_core_comprehensive.py` (kept `TestProjectManager`,
> which tests live code). The real `DMS` in `service.py` is the only `DMS`
> import path (`backend.services.dms` package `__init__` already exported it;
> the `backend/api/routers/dms.py` router is a different, live file). GitNexus
> impact analysis before the deletion: dead class = LOW risk (importers were
> only `dms_memory.py` + 3 test files), `DMSMemory` = zero production callers.
> DMS suite after: 166 passed / 24 skipped / 2 xfailed, with only the known
> pre-existing order-dependent `test_list_manual_rag_empty` failure.
`backend/services/dms/dms.py` defines a second `DMS` (constructor incompatible with the real one: `DMSVectorStore(vs_config)` passes a **dict where a `Path` is required** → instant `TypeError`; `DMSDB()` with no path → `memory/dms.db` in CWD; `asyncio.run()` inside `upload_document` — crashes in any async context). It is imported only by `dms_memory.py`, which is imported by nothing in danwa-core (only tests). This is dead code that will detonate the moment someone "helpfully" wires it up — and its mere existence makes `from backend.services.dms.dms import DMS` a plausible-looking, wrong import. **Recommendation:** delete both files and port any `DMSMemory` consumers (the danwa legacy `src/dms/` tree already duplicates them) to `DMS` + `RAGContextFormatter` from `service.py`. If a memory facade is genuinely wanted, implement it as a thin adapter over the real `DMS`.

### 3.4 One cache, one key type

`_dms_cache` mixes string keys (projects, from `get_dms_for_project`) and tuple keys `("case", tenant, case)` (from `_get_dms_for_case` and `agent_worker`) in a single dict. It works, and `test_get_dms_for_project_uses_string_key` blesses it, but every consumer must know both conventions; the agent worker hand-rolls its own copy of the cache-insertion logic (including the tenant-from-path extraction and config swallowing) instead of calling a shared factory — that is three implementations of "get DMS for case" (router, agent worker, `get_dms_for_project`). **Recommendation:** one factory `get_dms_for_case(tenant_id, case_id)` in `service.py`, used by the router, the agent worker, and (post-§2.1) the debate path; keys either all-tuple or all-scope-id-string. This also deletes the agent worker's duplicated logic.

### 3.5 `rag_context.session_id` is not a session id

The `rag_context` table's `session_id` column stores the *project/scope id* (service.py: `self.db.add_rag_context(self._project_id, document_id)`), not any session. Anyone reading the schema or adding actual per-session RAG will be misled; the split-brain additionally means the same logical case can have rows under two different "session ids" (raw UUID and scope id). **Recommendation:** rename the column to `scope_id` in the same migration as §2.1, and keep the in-memory set only as a cache of the persisted truth (hydrate-on-miss rather than hydrate-once-at-init, so selections made by another process/route appear without restart).

### 3.6 The swallow-and-return-empty error culture is why these bugs shipped

Nearly every layer of the RAG stack catches broad exceptions and returns `[]`/`""`/`False`: `HybridRetriever._fetch_chunks_uncached`, `_bm25_retrieve`, `vector_store.search` (warning + `[]`), `DMS.get_rag_context`, `auto_retrieve_for_topic`, `dms_memory` (all methods), `resolve_rag_context` callers (each wraps in try/except and logs at *warning/debug*), `_get_dms_for_case` and `get_dms_for_project` (`load_dms_config` failure → `{}` — an invalid `settings.yaml` silently disables OCR and changes chunking defaults), `agent_worker._get_document_chunks` (debug-level swallow). The metadata_index docstring even records the archetype: a Chroma error "used to be swallowed and silently returned `[]`". Empty-vs-error is precisely the ambiguity that let the split-brain look like "RAG just finds nothing relevant". **Recommendation, pragmatic:** keep degradation (RAG must not 500 a debate), but (a) distinguish "no data" from "query failed" in the API shape (`{"results": [], "warning": "..."}`), (b) log retrieval failures at WARNING with the scope id and chunk count for the case's Chroma collection (one line: `case X: chroma has 0 chunks for project_id Y` would have made §2.1 obvious in the first support ticket), and (c) stop swallowing *config* errors — a malformed `settings.yaml` should fail startup loudly.

### 3.7 Inter-repo wiring nits (cheap fixes, real blast radius)

- **`.env` symlink:** `danwa/.env` → `danwa-core/.env`. Works, but means the frontend repo's behavior depends on a file owned by another repo; a checkout of danwa alone is broken. Prefer: danwa ships `.env.example`, `manage.sh` reads env from `../danwa-core/.env` explicitly and says so in an error when missing.
- **Sibling-directory assumptions:** `manage.sh` hardcodes `../danwa-core/manage.sh`; studio's vite proxy hardcodes `http://localhost:8000`. Make the backend URL an env (`DANWA_CORE_URL`) and print a clear error when the sibling is absent rather than a stack trace.
- **Committed build artifacts:** danwa-core has **194 `__pycache__` files tracked in git** (repo shows dirty status from them). Add `.gitignore` entries and `git rm -r --cached`.
- **`get_case_dir` negative cache never invalidates:** once a case id 404s (e.g. queried right before the case directory was created), it stays negative until process restart. Either cap the negative cache with a TTL or drop negative entries on case creation.
- **`get_case_store`/`get_project_store` resolution duplication:** the case-scoped router validates tenant→case via `CaseStore.get(tenant_id, case_id)` while the debate path trusts `X-Case-Id` + `ProjectStore` — two resolution paths for the same concept; after §2.1/§2.7 route everything through one helper that also returns the canonical scope id.

### 3.8 Where the architecture is genuinely sound (keep it)

For balance: the per-case physical isolation (own `dms.db` + own `chroma_db` directory) is the right call and makes the §2.1 fix a namespace problem, not a data-partition problem; the `metadata_index` multi-tenant docstrings and `hybrid_retriever`'s BM25 corpus cap (`MAX_BM25_CORPUS_SIZE`, with rationale) show good instincts; the deprecation-header middleware on legacy routes is a clean migration affordance; and the frontend's `_ctx()` route-selection pattern is tidy and testable.

---

## 4. Performance & Resilience Optimizations

1. **Event-loop offloading (pairs with §2.2).** Beyond uploads, `DMSVectorStore.__init__` runs `get_or_create_collection` and `collection.count()` on **every** `DMS` construction — and with the split-brain there are two constructions per case per process. Post-fix there's one cached instance per case, but the first request touching each case pays Chroma client setup inline; move first-touch into a warmup or lazy background init.
2. **Cross-encoder load at import time.** `HybridRetriever.__init__` constructs `CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")` synchronously for every DMS instance (per case!) — currently downloading/loading weights per case directory until cached by sentence-transformers' global cache, and it silently disabled here ("sentence_transformers not installed"). Make it lazy (load on first rerank) and module-level shared, so N cases don't attempt N loads.
3. **Chroma's default embedding function.** `DMSVectorStore` relies on Chroma's built-in default embedding (ONNX MiniLM) — first query per process downloads the model; `config.py` declares `embedding_model: intfloat/multilingual-e5-small` but **nothing consumes it**. Either wire the configured model explicitly or remove the config to stop promising it.
4. **BM25 rebuild cost.** `_fetch_chunks_uncached` pulls the full project corpus (`get_chunks_by_project`) and builds `BM25Okapi` on the request thread every 5 minutes per project; the corpus cap (10k) bounds it, but with the corpus in memory already, building could move to a background thread and swap the cache atomically. Low urgency — the cap already removed the DoS vector.
5. **Upload memory spike.** Both upload routes do `content = await file.read()` — the entire file in RAM before any size check (the legacy route checks the limit only *after* reading; the case-scoped route has **no size check at all**, so `max_file_size_mb` is unenforced there). Stream to disk (`await file.seek(0)` chunked copy or `shutil.copyfileobj` over an async wrapper) and enforce `max_file_size_mb` in the case-scoped route explicitly:

   ```python
   max_bytes = dms_config.get("max_file_size_mb", 50) * 1024 * 1024
   size = int(file.headers.get("content-length", 0))
   if size > max_bytes:
       raise HTTPException(413, ...)
   ```

6. **Temp-file hygiene.** The case-scoped upload deletes its temp file in `finally`, good — but the legacy route deletes `tmp_path` only on some paths; ensure `finally: os.unlink(tmp_path)` there too (an aborted OCR run otherwise leaves multi-hundred-MB temp orphans in `/tmp`).
7. **Stale-instance resilience.** `_reset_stale_running_debates()` at startup is a nice touch; consider the same for DMS: at startup, per case, if `documents.word_count == 0` and chunks are missing (ingestion interrupted by the 300 s timeout or a crash), re-queue ingestion. Today a timed-out upload leaves a permanent zombie document row — invisible to RAG, listed in the UI, which is *another* face of the "file unreadable" complaint.
8. **`ProfileService`/`UserKeyStore` construction per request.** Prior-session findings in the danwa legacy tree (fresh SQLite connection + DDL per request in `UserKeyStore.__init__`, `ProfileService()` re-reading the DB each call) — verify the danwa-core equivalents and hoist to app-lifetime singletons via `@lru_cache` deps; the pattern is already established in `deps.py` for stores.

> **Remediation status (2026-09-02, danwa-core `2e54b6d`):** §4.1–§4.8 are
> implemented (§4.6 had already been fixed by the §2.2 upload rewrite —
> `finally: os.unlink(tmp_path)` on the legacy route — and needed no change).
> **§4.1** — `DMSVectorStore.__init__` performs zero Chroma I/O; first use
> goes through `_ensure_initialized()` (RLock, double-checked) which assigns
> the client only after the collection is usable, so a failed init retries
> on the next call; every operation goes via the `collection` property.
> **§4.2** — the cross-encoder is a module-level shared lazy singleton
> (`_get_cross_encoder()` with a failed-load flag); `HybridRetriever` is now
> cheap to construct, and the per-instance `cross_encoder` property remains
> settable as a test seam. **§4.3** — removed (not wired): `embedding_model`
> from `DEFAULT_DMS_CONFIG`; collections keep Chroma's default ONNX MiniLM EF
> — switching EFs on existing collections would silently corrupt retrieval.
> **§4.4** — instead of a background thread, the BM25 build is single-flight
> under `_corpus_cache_lock`: first caller builds, concurrent callers wait
> and reuse; TTL semantics and the 10k corpus cap are unchanged, and the
> cap bounds the locked build to well under a second (the report itself
> downgraded urgency once capped). **§4.5** — both upload routes stream to
> disk in 1 MiB chunks with a running total and abort with 413 the moment
> `max_file_size_mb` is exceeded; the case-scoped route (previously with **no
> size check at all**) now enforces the same cap and 413 detail format; temp
> files are unlinked on every exit path. **§4.7** — the zombie signal is
> **zero chunks** (`NOT EXISTS(document_chunks)`; pre-fix rows legitimately
> have `word_count=0` *with* chunks), not `word_count==0` as originally
> suggested; `main._requeue_zombie_documents()` runs at startup, re-ingests
> rows whose `file_path` still exists via the new
> `service.reingest_document(doc_id)`, and marks
> `metadata_json.failed_ingest` on the rest (UI-visible reason, rows never
> deleted). **§4.8** — one global `ProfileService` via
> `profile_service.get_shared_profile_service()`, shared by `deps`, both
> profile routers, `node_functions`/`legacy_nodes`, and as the default for
> `LLMService`/`TranslationService`/`AssistantService` (explicit
> `profile_service=`/`db_path=` params keep tests isolated); per-case
> services go through `deps.get_profile_service_for_case_cached` and are
> invalidated by `ProjectStore.update` so config writes are seen on the next
> request; `UserKeyStore` is a `deps.get_user_key_store()` singleton (lazy
> import so class-level test patches stay effective) and the BYOK router
> uses it. Verified by parity runs against the pre-change baseline
> (identical pre-existing failure sets; GitNexus flagged the expected
> CRITICAL change breadth — 68 symbols, 123 processes — with no behavioral
> regressions).

---

## 5. Clarifying Questions

1. **Namespace decision (§2.1):** Do you want the quick unification on the synthetic `case:{t}:{c}` scope (Option A, minimal blast radius) or the cleaner removal of the synthetic namespace in favor of raw case UUIDs (Option B, needs a Chroma+SQLite backfill)? Either works — but the choice determines whether the backfill rewrites all existing chunk metadata or only the debate-path callers.
2. **DMS authentication (§2.7):** Is the absence of auth on DMS/case-scoped routes a deliberate interim state (e.g. because interactive agents or external tools call these APIs without identities), or an oversight to fix now? If agents need access, should they carry a service token, or should the interactive worker use the case DMS in-process (as `_get_document_chunks` already does) so no agent ever calls the HTTP surface?
3. **Migration window for the data backfill:** are there deployments whose case DMS data was produced by *both* routes (documents uploaded pre-migration via legacy `X-Case-Id` flow tagging raw UUIDs, and later via case-scoped flow tagging scope ids)? If so, the backfill (§2.1.1) must normalize both tag styles, and I'd like a sample `dms.db` + `chroma_db` from production to confirm the migration handles both before you ship it.

---

*Report grounded in: case_scoped.py, dms.py (router), service.py, dms.py (class), dms_memory.py, rag_pipeline.py, document_processor.py, doc_parser.py, chunker.py, database.py, vector_store.py, metadata_index.py, hybrid_retriever.py, config.py, debate_rag.py, debate_workflow.py, workflow_exec.py, input_composer.py, agent_worker.py, deps.py, project_store.py, main.py, multitenant-isolation tests, frontend document.js/debate.js/core.js/DocumentsView.svelte, and repo-level checks across all four repositories. The split-brain reproduction script is available on request.*
