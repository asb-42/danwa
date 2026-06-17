"""Regression test: workspace.py's get_workspace_summary must use
the same project_id as the case-scoped DMS for list_documents().

Background
----------
After the 2026-06-17 RAG-scope unification, the case-scoped DMS
binds documents under the bare ``case_id`` (not the synthetic
``f"case:{tenant_id}:{case_id}"`` scope).  workspace.py was
still using the old synthetic scope in its document-count
query, so the count was always 0 — matching the user-reported
"'Documents 0' for cases that have 52 documents" bug.

The fix: workspace.py now calls ``dms.list_documents(case_id)``
(the same project_id the DMS was bound to).

This test pins the invariant.
"""

from __future__ import annotations

import re
from pathlib import Path

WORKSPACE_PY = Path(__file__).resolve().parents[2] / "backend" / "api" / "routers" / "workspace.py"


def test_workspace_summary_uses_bare_case_id_for_list_documents():
    """workspace.py's document-count call must use the bare case_id,
    not the synthetic ``f"case:{tenant_id}:{case_id}"`` scope.
    """
    src = WORKSPACE_PY.read_text(encoding="utf-8")
    # Find the list_documents call in the workspace summary branch.
    matches = re.findall(
        r"dms\.list_documents\(([^)]+)\)",
        src,
    )
    assert matches, "Could not find any dms.list_documents(...) call in workspace.py.  Did the function get renamed?"

    for arg in matches:
        assert 'f"case:' not in arg, (
            f"workspace.py is calling dms.list_documents({arg!r}) "
            "with the legacy synthetic scope.  The case-scoped DMS "
            "now binds project_id to the bare case_id (see "
            "_get_dms_for_case), so this call returns 0 documents.  "
            "Use the bare case_id instead."
        )
        # The arg must reference the case_id variable somewhere
        # (either directly or via a local alias).
        assert "case_id" in arg, (
            f"workspace.py is calling dms.list_documents({arg!r}) "
            "with a project_id that does not reference case_id.  "
            "This is almost certainly a bug — the workspace summary "
            "is per-case, so the project_id must be the case_id."
        )


def test_workspace_summary_does_not_construct_synthetic_case_scope():
    """Defence-in-depth: no LIVE code (non-comment) builds the
    legacy ``f"case:{tenant_id}:{case_id}"`` scope inside
    workspace.py.  The case-scoped DMS no longer uses that
    namespace.  Comments that mention the historical scope are
    OK (they document what NOT to do).
    """
    src = WORKSPACE_PY.read_text(encoding="utf-8")
    # Strip Python line comments before scanning so explanatory
    # comments like "this used to use f\"case:{...}\" don't
    # trigger the test.
    non_comment_lines = [line for line in src.splitlines() if not line.lstrip().startswith("#")]
    non_comment = "\n".join(non_comment_lines)
    # Look for the pattern f"case:..." in live code only.
    legacy = re.findall(r'f"case:\{[^}]+\}:\{[^}]+\}"', non_comment)
    assert not legacy, (
        f"workspace.py contains the legacy synthetic scope {legacy} "
        "in live code.  The case-scoped DMS no longer uses this "
        "namespace — use the bare case_id everywhere instead."
    )
    legacy_sq = re.findall(r"f'case:\{[^}]+\}:\{[^}]+\}'", non_comment)
    assert not legacy_sq, f"workspace.py contains the legacy synthetic scope {legacy_sq} in live code (single quotes).  See comment above."
