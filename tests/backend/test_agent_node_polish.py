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
"""

from __future__ import annotations

import inspect

from backend.workflow.nodes import agent_nodes
from backend.workflow.nodes.agent_nodes import agent_node_factory


class TestL1DeadCodeRemoved:
    """Verify the dead ``blueprint_name`` lookup is gone."""

    def test_blueprint_name_lookup_removed(self) -> None:
        """The source must not contain the discarded
        ``resolved_config.get(\"blueprint_name\", role)`` expression.
        """
        import re
        from pathlib import Path

        src = (Path(__file__).resolve().parents[2] / "backend" / "workflow" / "nodes" / "agent_nodes.py").read_text(
            encoding="utf-8"
        )
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
    """Verify the truncation constants are now module-level."""

    def test_max_draft_len_is_module_constant(self) -> None:
        """``_MAX_DRAFT_LEN`` must live at module level (not buried
        inside a function) and equal the historical value of 50000.
        """
        assert hasattr(agent_nodes, "_MAX_DRAFT_LEN")
        assert agent_nodes._MAX_DRAFT_LEN == 50000

    def test_truncation_marker_is_module_constant(self) -> None:
        """``_DRAFT_TRUNCATION_MARKER`` is the explicit truncation
        string — must be importable from the module.
        """
        assert hasattr(agent_nodes, "_DRAFT_TRUNCATION_MARKER")
        assert "content truncated" in agent_nodes._DRAFT_TRUNCATION_MARKER
        assert agent_nodes._DRAFT_TRUNCATION_MARKER.startswith("\n\n")
        assert agent_nodes._DRAFT_TRUNCATION_MARKER.endswith("\n\n")

    def test_function_local_constants_gone(self) -> None:
        """The old function-local ``_max_draft_len = 50000`` and
        ``_trunc_warn = \"\\n\\n[… content truncated …]\\n\\n`` must
        be gone from inside ``agent_node_factory``.
        """
        import textwrap

        src = textwrap.dedent(inspect.getsource(agent_node_factory))
        assert "_max_draft_len = 50000" not in src
        assert "_trunc_warn =" not in src
