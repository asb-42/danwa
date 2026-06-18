"""Regression test: start_mvp_debate must pass ``dms_project_id`` to
``resolve_rag_context`` so the case-scoped DMS is found.

Background
----------
On 2026-06-18 the user reported that MVP-debate agents
answered with "no RAG access" even though the case had
51 documents indexed.  Root cause:

  * The MVP path (backend.api.routers.workflow_exec:
    start_mvp_debate) called resolve_rag_context with only
    project_id=case_id.
  * The case-scoped DMS uses the bare case_id as its
    project_id (commit 758a9b0), but the RAG resolver
    computes the dms_project_id from a separate parameter
    (or falls back to project_id).  When the resolver
    calls ``get_dms_for_project(dms_project_id)`` and the
    case_id is unknown to the legacy ProjectStore, it
    raises ``Project not found`` and the resolver returns
    ``""`` for the RAG context — the agent sees no documents.

The fix: pass ``dms_project_id=effective_project_id`` (which
IS the bare case_id) to resolve_rag_context.  This makes
the RAG resolver query the case-scoped DMS with the right
namespace, and the 51 documents are returned.

This test guards the call site so a future refactor cannot
silently drop the dms_project_id and re-introduce the
"no RAG access" bug.

Implementation note
-------------------
We deliberately **do not** import ``backend.api.routers.workflow_exec``
here.  That module transitively imports ``sse_starlette`` (used for
the SSE stream response), which is not always installed in the
slim test environment.  Instead we use :mod:`ast` to parse the file
and extract the function's source text.  ``ast`` parses syntax
without executing imports, so this works regardless of which
optional runtime dependencies are available.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_EXEC_PATH = _PROJECT_ROOT / "backend" / "api" / "routers" / "workflow_exec.py"


def _extract_start_mvp_debate_source() -> str:
    """Return the source text of ``start_mvp_debate`` from disk.

    Uses :mod:`ast` to locate the function.  This avoids importing
    the module, which would transitively pull in ``sse_starlette``.
    """
    assert _WORKFLOW_EXEC_PATH.is_file(), (
        f"workflow_exec.py not found at {_WORKFLOW_EXEC_PATH} - did the file move?  Update the test to point at the new location."
    )

    source = _WORKFLOW_EXEC_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_WORKFLOW_EXEC_PATH))
    func: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "start_mvp_debate":
            func = node
            break

    assert func is not None, (
        f"Could not find 'def start_mvp_debate(' in {_WORKFLOW_EXEC_PATH}.  "
        f"Did the function get renamed or moved?  This regression test "
        f"guards the MVP-debate RAG call site - update it to point at "
        f"the new location."
    )

    # ``ast.get_source_segment`` returns the exact text of the node,
    # including decorators.  Decorators are fine for our static guards
    # - we only care that the call site is present in the body.
    segment = ast.get_source_segment(source, func, padded=True)
    assert segment is not None, (
        "ast could not extract the source segment for start_mvp_debate.  "
        "This usually means the file uses syntax that the running "
        "Python version cannot parse."
    )
    return segment


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_start_mvp_debate_passes_dms_project_id_to_resolve_rag_context():
    """start_mvp_debate must pass ``dms_project_id`` so the
    case-scoped DMS is found.
    """
    src = _extract_start_mvp_debate_source()

    assert "resolve_rag_context(" in src, (
        "start_mvp_debate no longer calls resolve_rag_context - did the function get refactored to a different RAG lookup?"
    )

    assert "dms_project_id" in src, (
        "start_mvp_debate no longer passes dms_project_id to "
        "resolve_rag_context.  Without it, the case-scoped DMS "
        "lookup raises 'Project not found' and the MVP-debate "
        "agents answer with 'no RAG access' even though the case "
        "has documents indexed.  Pass dms_project_id=case_id (or "
        "equivalent) so the RAG resolver finds the documents."
    )

    # Defensive: the dms_project_id must equal the case_id (which
    # in the case-scoped DMS is the canonical namespace key).
    # We don't enforce a specific value, but the parameter must
    # reference the case id (e.g. effective_project_id or a
    # derived value).
    assert "dms_project_id=effective_project_id" in src or "dms_project_id=project_id" in src, (
        "start_mvp_debate calls resolve_rag_context with "
        "dms_project_id, but the value is not derived from the "
        "case_id.  The case-scoped DMS uses the bare case_id as "
        "its project_id, so dms_project_id must equal the "
        "case_id (effective_project_id / project_id)."
    )


def test_resolve_rag_context_signature_includes_dms_project_id():
    """The dms_project_id parameter must exist on resolve_rag_context.

    This is a structural guard - if a future refactor renames or
    drops the parameter, the test fails before production.

    Note: ``backend.services.debate.debate_rag`` has lightweight
    imports (no sse_starlette), so importing it directly is safe.
    """
    import inspect

    debate_rag = importlib.import_module("backend.services.debate.debate_rag")
    sig = inspect.signature(debate_rag.resolve_rag_context)
    assert "dms_project_id" in sig.parameters, (
        "resolve_rag_context no longer accepts a dms_project_id "
        "parameter.  This breaks the MVP-debate RAG pipeline "
        "because the case-scoped DMS namespace is not the bare "
        "case_id by default."
    )
    # The parameter must accept a default of None (so legacy
    # callers don't have to pass it).
    default = sig.parameters["dms_project_id"].default
    assert default is None, f"dms_project_id default should be None (backward compatible), got {default!r}"
