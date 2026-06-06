"""Tests for Sprint 35 (L1 + L2) — dead code removal + magic-number hoist.

L1: ``agent_nodes.py:73`` had ``resolved_config.get("blueprint_name",
role)`` whose result was immediately discarded — pure dead code.
Sprint 35 deletes it and adds a comment explaining where the
``blueprint_name`` documentation lives.

L2: The function-local ``_max_draft_len = 50000`` (with the matching
``"\n\n[\\u2026 content truncated \\u2026]\n\n"`` marker) was a magic
number buried inside a 50-line function.  Sprint 35 promotes both to
module-level constants so the truncation policy lives in one
discoverable place.

Sprint 39 (H2 fix): the constants and the truncation logic moved
to ``backend.workflow.nodes._draft_helpers`` so the
``interjection_node`` and the legacy ``run_agent_node`` apply the
same bound.  These tests now point to the new home of the
constants.
"""

from __future__ import annotations

import inspect

from backend.workflow.nodes.agent_nodes import agent_node_factory


class TestL1DeadCodeRemoved:
    """Verify the dead ``blueprint_name`` lookup is gone."""

    def test_blueprint_name_lookup_removed(self) -> None:
        """The source must not contain the discarded
        ``resolved_config.get(\"blueprint_name\", role)`` expression.
        """
        import re
        from pathlib import Path

        src = (Path(__file__).resolve().parents[2] / "backend" / "workflow" / "nodes" / "agent_nodes.py").read_text(encoding="utf-8")
        # The expression had no useful effect — discard it
        assert not re.search(
            r"resolved_config\.get\(\s*[\"\']blueprint_name[\"\']\s*,\s*role\s*\)",
            src,
        )

    def test_blueprint_name_still_documented(self) -> None:
        """The agent_node_factory docstring must still mention
        ``blueprint_name`` as a recognised key so workflow authors
        aren't surprised when they don't see it used in code.
        """
        doc = agent_node_factory.__doc__ or ""
        assert "blueprint_name" in doc


class TestL2MagicNumberHoisted:
    """Verify the truncation constants are now module-level.

    Sprint 39 (H2 fix): the constants now live in
    ``backend.workflow.nodes._draft_helpers`` so all three
    accumulators share the same bound.  ``agent_nodes`` no longer
    holds its own copy.
    """

    def test_max_draft_len_is_module_constant(self) -> None:
        """``MAX_RUNNING_DRAFT_LEN`` must live at module level
        (not buried inside a function) and equal the historical
        value of 50000.  Located in the shared ``_draft_helpers``
        module since Sprint 39.
        """
        from backend.workflow.nodes import _draft_helpers

        assert hasattr(_draft_helpers, "MAX_RUNNING_DRAFT_LEN")
        assert _draft_helpers.MAX_RUNNING_DRAFT_LEN == 50000

    def test_truncation_marker_is_module_constant(self) -> None:
        """``RUNNING_DRAFT_TRUNCATION_MARKER`` is the explicit
        truncation string — must be importable from the shared
        module.
        """
        from backend.workflow.nodes import _draft_helpers

        marker = _draft_helpers.RUNNING_DRAFT_TRUNCATION_MARKER
        assert "content truncated" in marker
        assert marker.startswith("\n\n")
        assert marker.endswith("\n\n")

    def test_agent_nodes_uses_shared_helper(self) -> None:
        """Sprint 39 (H2): ``agent_nodes`` must delegate the
        truncation to the shared helper, not re-implement it.
        The source of ``agent_node_factory`` must not contain
        a hand-rolled head+tail computation.
        """
        src = inspect.getsource(agent_node_factory)
        assert "_MAX_DRAFT_LEN" not in src
        assert "head + _DRAFT_TRUNCATION_MARKER + tail" not in src
        assert "truncate_running_draft" in src

    def test_function_local_constants_gone(self) -> None:
        """The old function-local ``_max_draft_len = 50000`` and
        ``_trunc_warn = \"\\n\\n[… content truncated …]\\n\\n`` must
        be gone from inside ``agent_node_factory``.
        """
        import textwrap

        src = textwrap.dedent(inspect.getsource(agent_node_factory))
        assert "_max_draft_len = 50000" not in src
        assert "_trunc_warn =" not in src
