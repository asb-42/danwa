"""Regression tests for the RAG scope_id vs case_id namespace mismatch.

Background
----------
The case-scoped DMS used to bind documents under a synthetic scope id
``f"case:{tenant_id}:{case_id}"`` (defence-in-depth against cross-tenant
collisions).  The legacy debate workflow, however, always passes the
bare ``case_id`` to ``resolve_rag_context`` / ``get_dms_for_project``.
Result: ChromaDB ``where={"project_id": case_id}`` queries returned zero
chunks, and the agents replied with ``"Dokument nicht im RAG abrufbar"``.

The fix is twofold:
1. The case-scoped DMS now binds to the bare ``case_id`` (which is a
   UUID, so cross-tenant collision is impossible in practice — the
   per-case directory layout already provides isolation).
2. The ``_case_scope_id()`` helper now returns the bare ``case_id`` as
   an alias, so any caller that still passes the historical scope id
   silently degrades to the correct value.

These tests pin both behaviours so a future refactor cannot silently
regress.
"""

from __future__ import annotations

import importlib
import sys
import types
from unittest import mock

# ---------------------------------------------------------------------------
# Lightweight in-memory DMS stub (no real chromadb required for the
# namespace assertions in this test).
# ---------------------------------------------------------------------------


class _StubVectorStore:
    """Captures added chunks and serves them by ``where`` filter."""

    def __init__(self) -> None:
        self._docs: list[dict] = []

    def add_chunks(
        self,
        document_id: str,
        chunks: list[dict],
        project_id: str = "",
    ) -> None:
        for idx, chunk in enumerate(chunks):
            self._docs.append(
                {
                    "id": f"{document_id}_chunk_{idx}",
                    "text": chunk["text"],
                    "metadata": {
                        "document_id": document_id,
                        "project_id": project_id,
                        "chunk_index": idx,
                    },
                }
            )

    def search(self, query: str, project_id=None, k: int = 5) -> list[dict]:
        return [d for d in self._docs if project_id is None or d["metadata"].get("project_id") == project_id][:k]

    def collection(self):  # pragma: no cover - not used in these tests
        return mock.MagicMock()


class _StubMetadataIndex:
    """Reproduces the ``get_chunks_by_document`` behaviour the RAG
    pipeline depends on, but as an in-memory dict instead of ChromaDB."""

    def __init__(self, project_id: str) -> None:
        self._project_id = project_id
        self._vs = _StubVectorStore()

    def get_chunks_by_document(self, document_id: str) -> list[dict]:
        return [d for d in self._vs._docs if d["metadata"].get("document_id") == document_id and d["metadata"].get("project_id") == self._project_id]


def _build_dms(project_id: str) -> types.SimpleNamespace:
    """Construct a minimal DMS-shaped object for the assertions."""
    vs = _StubVectorStore()
    mi = _StubMetadataIndex(project_id=project_id)

    def _format(chunks, max_chars=None):
        out = "".join(f"[Document {i + 1}]: {c['text']}\n\n" for i, c in enumerate(chunks))
        if max_chars and len(out) > max_chars:
            out = out[: max_chars - 3] + "..."
        return out

    return types.SimpleNamespace(
        _project_id=project_id,
        vector_store=vs,
        metadata_index=mi,
        rag_formatter=mock.MagicMock(),
        format_rag_context=_format,
    )


# ---------------------------------------------------------------------------
# 1. _case_scope_id / _get_dms_for_case invariants
# ---------------------------------------------------------------------------


def test_case_scope_id_returns_bare_case_id():
    """``_case_scope_id`` MUST equal ``case_id`` after the fix.

    A future refactor that re-introduces the synthetic
    ``case:{tid}:{cid}`` scope here will silently break every
    case-scoped RAG query — this test guards against that.
    """
    from backend.api.routers.case_scoped import _case_scope_id

    case_id = "abc-123"
    tenant_id = "_default"
    assert _case_scope_id(tenant_id, case_id) == case_id, (
        "_case_scope_id must return the bare case_id (not the synthetic "
        "f'case:{tenant_id}:{case_id}') so that the legacy debate "
        "workflow's RAG queries can find case-scoped chunks."
    )


def test_case_scoped_dms_project_id_is_bare_case_id(monkeypatch, tmp_path):
    """``_get_dms_for_case`` MUST bind the DMS to the bare case_id.

    Verifies the fix for the regression by patching the heavy
    ``DMS`` constructor and asserting the ``project_id`` it receives.
    """
    from backend.api.routers import case_scoped

    case_id = "case-xyz"
    tenant_id = "_default"

    # Build a real Case object so _get_dms_for_case's existence check
    # passes without needing a real case store on disk.
    from backend.models.case import Case

    case = Case(id=case_id, tenant_id=tenant_id, title="T", description="")

    fake_case_store = mock.MagicMock()
    fake_case_store.get.return_value = case
    fake_case_store.get_case_dir.return_value = tmp_path

    captured: dict = {}

    def fake_dms_ctor(
        db_path,
        chroma_path,
        config=None,
        project_id=None,
    ):
        captured["project_id"] = project_id
        captured["db_path"] = db_path
        captured["chroma_path"] = chroma_path
        return mock.MagicMock(_project_id=project_id)

    # ``DMS`` is imported lazily inside ``_get_dms_for_case`` so we
    # patch the symbol at its source module.
    monkeypatch.setattr(
        "backend.services.dms.service.DMS",
        fake_dms_ctor,
    )

    case_scoped._get_dms_for_case(tenant_id, case_id, fake_case_store)

    assert captured["project_id"] == case_id, (
        f"_get_dms_for_case bound project_id={captured['project_id']!r} "
        f"instead of the bare case_id.  This re-introduces the "
        f"namespace mismatch that caused the RAG regression."
    )


# ---------------------------------------------------------------------------
# 2. resolve_rag_context end-to-end with a stubbed DMS layer
# ---------------------------------------------------------------------------


def test_resolve_rag_context_finds_chunks_under_bare_case_id(monkeypatch, tmp_path):
    """Simulates the legacy debate workflow that passes only the case_id.

    Even though the chunks were indexed by the case-scoped upload flow
    (which used to use a synthetic scope id and now uses the bare
    case_id), ``resolve_rag_context(case_id)`` must find them.

    Setup:
      - a case-scoped DMS instance bound to project_id = case_id
      - one document indexed under project_id = case_id
      - ``resolve_rag_context(project_id=case_id, document_ids=[doc_id])``
        is called
      - the resolved RAG context must contain the chunk text
    """
    from backend.services.debate import debate_rag

    case_id = "case-abc"
    doc_id = "doc-1"

    # Build a stub DMS that exposes only what resolve_rag_context uses.
    dms = _build_dms(project_id=case_id)
    dms.metadata_index._vs.add_chunks(
        document_id=doc_id,
        chunks=[{"text": "VERIFICATION TEXT", "chunk_index": 0, "file_name": "f.txt"}],
        project_id=case_id,
    )

    # Patch the factory + the document-analysis loader so the function
    # body uses our stub.
    monkeypatch.setattr(
        "backend.services.dms.service.get_dms_for_project",
        lambda *a, **kw: dms,
    )
    monkeypatch.setattr(debate_rag, "_load_analysis_text", lambda *a, **kw: "")

    rag_context, doc_count = debate_rag.resolve_rag_context(
        project_id=case_id,
        case_text="irrelevant",
        document_ids=[doc_id],
    )

    assert "VERIFICATION TEXT" in rag_context, f"RAG context was empty — the case_id was not used to look up chunks.  Got: {rag_context!r}"
    assert doc_count == 1


def test_resolve_rag_context_uses_dms_project_id_override(monkeypatch, tmp_path):
    """Verifies the explicit ``dms_project_id`` override is honoured.

    Even if some upstream caller passes the historical synthetic scope
    id (defence-in-depth), ``resolve_rag_context`` must use it to
    resolve the DMS so the chunks are still findable.
    """
    from backend.services.debate import debate_rag

    case_id = "case-abc"
    scope_id = f"case:_default:{case_id}"  # legacy synthetic scope
    doc_id = "doc-1"

    dms = _build_dms(project_id=scope_id)
    dms.metadata_index._vs.add_chunks(
        document_id=doc_id,
        chunks=[{"text": "SCOPED TEXT", "chunk_index": 0, "file_name": "f.txt"}],
        project_id=scope_id,
    )

    monkeypatch.setattr(
        "backend.services.dms.service.get_dms_for_project",
        lambda project_id, *a, **kw: dms if project_id == scope_id else None,
    )
    monkeypatch.setattr(debate_rag, "_load_analysis_text", lambda *a, **kw: "")

    rag_context, _ = debate_rag.resolve_rag_context(
        project_id=case_id,
        case_text="irrelevant",
        document_ids=[doc_id],
        dms_project_id=scope_id,  # explicit override (the fix's safety hatch)
    )

    assert "SCOPED TEXT" in rag_context


# ---------------------------------------------------------------------------
# 3. Migration v024 — idempotent rewrite of legacy scope ids
# ---------------------------------------------------------------------------


def test_v024_migration_rewrites_synthetic_scope_ids(monkeypatch, tmp_path):
    """The v024 migration must rewrite project_id from
    ``case:{tid}:{cid}`` to the bare ``{cid}`` and be idempotent.
    """
    case_id = "case-abc"
    tenant_id = "_default"
    scope_id = f"case:{tenant_id}:{case_id}"

    # Build a fake tenants tree on disk.
    cases_root = tmp_path / "data" / "tenants" / tenant_id / "cases" / case_id
    chroma_dir = cases_root / "dms" / "chroma_db"
    chroma_dir.mkdir(parents=True)

    # Track per-document metadata.
    documents: dict[str, list[dict]] = {}

    class _FakeCollection:
        def __init__(self, name):
            self.name = name

        def get(self, include=None):
            ids, metas = [], []
            for doc_id, rows in documents.items():
                for r in rows:
                    ids.append(f"{doc_id}_chunk_{r['chunk_index']}")
                    metas.append(r)
            return {"ids": ids, "metadatas": metas}

        def update(self, ids, metadatas):
            for cid, meta in zip(ids, metadatas):
                doc_id, _, idx_str = cid.rpartition("_chunk_")
                idx = int(idx_str)
                for r in documents[doc_id]:
                    if r["chunk_index"] == idx:
                        r.update(meta)
                        break

    class _FakeClient:
        def __init__(self, path):
            self.path = path

        def list_collections(self):
            return [_FakeCollection("document_chunks")]

        def get_collection(self, name):
            return _FakeCollection(name)

    # Seed with one document indexed under the synthetic scope.
    documents["doc-1"] = [
        {
            "chunk_index": 0,
            "project_id": scope_id,
            "file_name": "f.txt",
            "text": "hello",
        }
    ]

    # Patch the chromadb module the migration imports lazily.
    fake_chromadb = types.SimpleNamespace(PersistentClient=_FakeClient)
    monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)

    # Import the migration (or re-use the cached one).
    importlib.invalidate_caches()
    if "backend.migrations.v024_rag_project_id_dedup" in sys.modules:
        del sys.modules["backend.migrations.v024_rag_project_id_dedup"]
    migration = importlib.import_module("backend.migrations.v024_rag_project_id_dedup")

    # Override the BASE constant AFTER import so our tmp_path is used.
    migration._TENANTS_BASE = tmp_path / "data" / "tenants"

    # First run: rewrites 1 chunk.
    n = migration.migrate(case_id=case_id)
    assert n == 1
    assert documents["doc-1"][0]["project_id"] == case_id
    assert documents["doc-1"][0]["_legacy_project_id"] == scope_id

    # Second run: idempotent (nothing left to rewrite).
    n2 = migration.migrate(case_id=case_id)
    assert n2 == 0


def test_v024_migration_ignores_already_migrated_chunks(monkeypatch, tmp_path):
    """Chunks already tagged with the bare case_id must be left alone."""
    case_id = "case-abc"
    tenant_id = "_default"

    cases_root = tmp_path / "data" / "tenants" / tenant_id / "cases" / case_id
    chroma_dir = cases_root / "dms" / "chroma_db"
    chroma_dir.mkdir(parents=True)

    documents: dict[str, list[dict]] = {"doc-1": [{"chunk_index": 0, "project_id": case_id}]}

    class _FakeCollection:
        def __init__(self, name):
            self.name = name

        def get(self, include=None):
            ids, metas = [], []
            for doc_id, rows in documents.items():
                for r in rows:
                    ids.append(f"{doc_id}_chunk_{r['chunk_index']}")
                    metas.append(r)
            return {"ids": ids, "metadatas": metas}

        def update(self, ids, metadatas):  # pragma: no cover
            pass

    class _FakeClient:
        def __init__(self, path):
            self.path = path

        def list_collections(self):
            return [_FakeCollection("x")]

        def get_collection(self, name):
            return _FakeCollection(name)

    monkeypatch.setitem(sys.modules, "chromadb", types.SimpleNamespace(PersistentClient=_FakeClient))
    if "backend.migrations.v024_rag_project_id_dedup" in sys.modules:
        del sys.modules["backend.migrations.v024_rag_project_id_dedup"]
    migration = importlib.import_module("backend.migrations.v024_rag_project_id_dedup")
    migration._TENANTS_BASE = tmp_path / "data" / "tenants"

    n = migration.migrate(case_id=case_id)
    assert n == 0
    assert documents["doc-1"][0]["project_id"] == case_id


# ---------------------------------------------------------------------------
# 5. Dispatch / workflow signature changes (round-trip the new arg)
# ---------------------------------------------------------------------------


def test_run_debate_workflow_accepts_dms_project_id():
    """Both ``run_debate_workflow`` and the inner helper must accept a
    ``dms_project_id`` parameter (or **dms_project_id) so the
    case-scoped path can pass the scope id.  This is a structural
    guard: a future refactor that drops the parameter will fail this
    test before it can break the RAG flow.
    """
    import inspect

    from backend.services import debate_workflow

    outer_sig = inspect.signature(debate_workflow.run_debate_workflow)
    inner_sig = inspect.signature(debate_workflow._run_debate_workflow_inner)
    build_sig = inspect.signature(debate_workflow.build_rag_preview)

    assert "dms_project_id" in outer_sig.parameters
    assert "dms_project_id" in inner_sig.parameters
    assert "dms_project_id" in build_sig.parameters
