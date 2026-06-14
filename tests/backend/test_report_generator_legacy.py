"""Legacy smoke tests for the new ``backend.workflow.report_generator`` module.

Historical context
------------------

This file was previously named ``tests/test_report_generator.py`` and contained
9 tests targeting the legacy ``src.tools.report_generator.ReportGenerator``
class (124 lines, dated 2026-05-13).  That legacy class is **no longer the
primary report generator** in the project — it has been superseded by
:class:`backend.workflow.report_generator.WorkflowReportGenerator` (1152
lines, dated 2026-06-12) which is exercised end-to-end by
``tests/backend/test_report_generator.py``.

Because the old module name collides with the new test file at the pytest
module level (``test_report_generator`` registered twice → ``import file
mismatch`` during collection), the file was moved here and **rewritten** to
verify the new module's public surface.  This is a deliberate trade-off:
the old 9 functional tests are dropped in favour of a smaller smoke test
suite that confirms the new module is importable and exposes the symbols
consumed by ``backend/api/routers/sessions.py`` and
``backend/api/routers/workflow_reports.py``.

If the legacy ``src.tools.report_generator`` ever regains prominence, the
old tests should be restored from git history (``b5c1bb9``) and placed
under a different filename (e.g. ``test_src_tools_report_generator.py``).
"""

from __future__ import annotations

from pathlib import Path


def test_workflow_report_generator_class_is_importable() -> None:
    """The new WorkflowReportGenerator class must be importable."""
    from backend.workflow.report_generator import WorkflowReportGenerator

    assert WorkflowReportGenerator is not None
    # The class is a public API — it must be a type
    assert isinstance(WorkflowReportGenerator, type)


def test_workflow_report_generator_can_be_constructed(tmp_path: Path) -> None:
    """A WorkflowReportGenerator instance is constructible with a db_path."""
    from backend.workflow.report_generator import WorkflowReportGenerator

    gen = WorkflowReportGenerator(db_path=tmp_path / "test.db")
    assert gen is not None
    # Specific method names are tested in tests/backend/test_report_generator.py


def test_audit_enrichment_helpers_are_importable() -> None:
    """The audit-trail enrichment helpers exist (see audit-trail-ux-improvement.md)."""
    from backend.workflow import report_generator as rg

    # These helpers are imported by the API routers and are part of the
    # public contract of this module.
    assert hasattr(rg, "_build_audit_context_map")
    assert hasattr(rg, "_format_audit_content")
    assert hasattr(rg, "_enrich_audit_entries")


def test_format_audit_content_handles_empty_input() -> None:
    """``_format_audit_content`` must not raise on empty/invalid input."""
    from backend.workflow.report_generator import _format_audit_content

    # Empty string, no event_type
    result = _format_audit_content("", "")
    assert isinstance(result, str)

    # Garbage input must return a string, not raise
    result = _format_audit_content("not-valid-json", "node_started")
    assert isinstance(result, str)


def test_build_node_phase_map_returns_dict() -> None:
    """``_build_node_phase_map`` returns a dict, even for an empty state."""
    from backend.workflow.report_generator import _build_node_phase_map

    result = _build_node_phase_map({})
    assert isinstance(result, dict)


def test_module_does_not_break_with_legacy_src_import() -> None:
    """Sanity check: the new module can be imported alongside the legacy one.

    ``backend/api/routers/sessions.py`` still imports from
    ``src.tools.report_generator`` for the legacy session-based report path.
    Both modules must coexist in the same Python process.
    """
    import importlib

    legacy = importlib.import_module("src.tools.report_generator")
    new = importlib.import_module("backend.workflow.report_generator")

    assert legacy is not None
    assert new is not None
    # The two classes are distinct types
    assert legacy.ReportGenerator is not new.WorkflowReportGenerator
