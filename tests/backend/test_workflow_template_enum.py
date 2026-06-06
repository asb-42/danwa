"""Tests for Sprint 30 (H4) — WorkflowTemplate StrEnum.

Verifies that the central :class:`WorkflowTemplate` StrEnum is the
single source of truth for template identifiers and that all
``workflow_template`` comparisons in production code use the enum
rather than the raw string literal.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from backend.workflow.workflow_state import WorkflowTemplate


class TestWorkflowTemplateEnum:
    """Verify the enum's values and string behaviour."""

    def test_enum_values_match_legacy_strings(self) -> None:
        """The enum values must be identical to the historical string
        literals so that state dicts serialised before the enum existed
        round-trip cleanly.
        """
        assert WorkflowTemplate.DEBATE == "debate"
        assert WorkflowTemplate.ACADEMIC_DEBATE == "academic_debate"
        assert WorkflowTemplate.TRANSACTIONAL_DRAFTING == "transactional_drafting"

    def test_enum_is_strenum(self) -> None:
        """WorkflowTemplate must be a StrEnum so that ``==`` against a
        plain string and ``f"{enum}"`` formatting both work as before.
        """
        from enum import StrEnum

        assert issubclass(WorkflowTemplate, StrEnum)

    def test_str_returns_raw_value(self) -> None:
        """``str(member)`` returns the raw string value, matching what
        gets stored in serialised state dicts.
        """
        assert str(WorkflowTemplate.TRANSACTIONAL_DRAFTING) == "transactional_drafting"

    def test_state_dict_compatibility(self) -> None:
        """Workflow state dicts store ``workflow_template`` as a plain
        string.  A direct comparison against the enum must still work
        (this is the entire point of using StrEnum).
        """
        state: dict = {"workflow_template": "transactional_drafting"}
        assert state["workflow_template"] == WorkflowTemplate.TRANSACTIONAL_DRAFTING
        assert WorkflowTemplate.TRANSACTIONAL_DRAFTING == state["workflow_template"]


class TestProductionCodeUsesEnum:
    """Static check: production code must not compare against the raw
    string literal ``"transactional_drafting"`` any more.

    We grep the source tree and fail if any production file (excluding
    the central definition and tests) still contains the bare literal
    in a comparison context.
    """

    @pytest.fixture()
    def backend_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "backend"

    def test_no_production_string_comparisons(self, backend_dir: Path) -> None:
        """No production file should compare against
        ``"transactional_drafting"`` as a string literal any more.
        The centralised :class:`WorkflowTemplate` enum is the single
        source of truth.
        """
        result = subprocess.run(
            [
                "grep",
                "-rn",
                "--include=*.py",
                "-E",
                r"== [" "'" '"]transactional_drafting[' "'" '"]|is [' "'" '"]transactional_drafting[' "'" '"]',
                str(backend_dir),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        # ``grep`` exits 1 when no match — that is what we want.
        assert result.returncode == 1, (
            "Production code still compares against the bare literal "
            '"transactional_drafting".  Use WorkflowTemplate.'
            f"TRANSACTIONAL_DRAFTING instead.\n{result.stdout}"
        )

    def test_print_plugin_remains_print_template_enum(self) -> None:
        """``PrintTemplate`` is a print-specific enum that happens to
        carry the same string value.  It must keep its own definition
        (the print template picker is a different concern from
        ``workflow_template``) but its ``TRANSACTIONAL_DRAFTING``
        value must equal the central ``WorkflowTemplate`` value.
        """
        from backend.services.output.plugins.print_plugin import PrintTemplate

        assert PrintTemplate.TRANSACTIONAL_DRAFTING == WorkflowTemplate.TRANSACTIONAL_DRAFTING
