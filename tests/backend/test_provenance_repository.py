"""Tests for Sprint 31 (H5) — provenance persistence via repository.

Verifies that :meth:`MiscRepository.save_provenance_batch` correctly
persists BuildResponse provenance rows to the ``build_response_provenance``
table — replacing the previous hardcoded ``Path("data/blueprints.db")``
inline sqlite3 connection in ``pragmatist_nodes.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.blueprints.repository import BlueprintRepository


@pytest.fixture()
def repo(tmp_path: Path) -> BlueprintRepository:
    """Fresh BlueprintRepository with temp database (runs migrations)."""
    return BlueprintRepository(db_path=tmp_path / "test_blueprints.db")


class TestSaveProvenanceBatch:
    """Verify save_provenance_batch inserts rows correctly."""

    def test_inserts_rows_with_full_provenance(self, repo: BlueprintRepository) -> None:
        """Each BuildResponse with a provenance sub-dict becomes one row."""
        build_responses = [
            {
                "response_to": "critic-1",
                "provenance": {
                    "draft_version": 2,
                    "critic_item_id": "ci-7",
                    "original_text": "Original text for clause 1",
                    "revision_type": "aggressive",
                    "pragmatist_verdict": "accept",
                    "pragmatist_score": 0.85,
                },
            },
            {
                "response_to": "critic-2",
                "provenance": {
                    "draft_version": 2,
                    "critic_item_id": "ci-8",
                    "original_text": "Original text for clause 2",
                    "revision_type": "conservative",
                    "pragmatist_verdict": "revise",
                    "pragmatist_score": 0.42,
                },
            },
        ]

        inserted = repo.save_provenance_batch("sess-1", "wf-1", build_responses)

        assert inserted == 2
        with repo._connect() as conn:  # noqa: SLF001 — test inspection
            rows = conn.execute(
                "SELECT response_to, draft_version, critic_item_id, "
                "original_text, revision_type, pragmatist_verdict, "
                "pragmatist_score FROM build_response_provenance "
                "ORDER BY response_to"
            ).fetchall()

        assert len(rows) == 2
        assert rows[0]["response_to"] == "critic-1"
        assert rows[0]["draft_version"] == 2
        assert rows[0]["critic_item_id"] == "ci-7"
        assert rows[0]["revision_type"] == "aggressive"
        assert rows[0]["pragmatist_verdict"] == "accept"
        assert rows[0]["pragmatist_score"] == 0.85
        assert rows[1]["response_to"] == "critic-2"
        assert rows[1]["pragmatist_verdict"] == "revise"

    def test_inserts_row_even_without_provenance(self, repo: BlueprintRepository) -> None:
        """BuildResponses with no provenance sub-dict still get a row,
        populated with column defaults — matches the historical
        behaviour of the inline ``sqlite3`` implementation.
        """
        build_responses = [
            {"response_to": "critic-1"},  # no provenance
            {
                "response_to": "critic-2",
                "provenance": {"draft_version": 1, "critic_item_id": "ci-1"},
            },
        ]

        inserted = repo.save_provenance_batch("sess-1", "wf-1", build_responses)

        assert inserted == 2
        with repo._connect() as conn:  # noqa: SLF001
            rows = conn.execute("SELECT response_to, draft_version, critic_item_id FROM build_response_provenance ORDER BY response_to").fetchall()
        assert len(rows) == 2
        # critic-1: defaults
        assert rows[0]["response_to"] == "critic-1"
        assert rows[0]["draft_version"] == 0
        assert rows[0]["critic_item_id"] == ""
        # critic-2: explicit values
        assert rows[1]["response_to"] == "critic-2"
        assert rows[1]["draft_version"] == 1
        assert rows[1]["critic_item_id"] == "ci-1"

    def test_uses_defaults_for_missing_provenance_fields(self, repo: BlueprintRepository) -> None:
        """Missing fields fall back to column defaults (0 / '' / 'conservative' / NULL)."""
        build_responses = [
            {
                "response_to": "critic-1",
                "provenance": {},  # all fields missing
            }
        ]

        inserted = repo.save_provenance_batch("sess-1", "wf-1", build_responses)

        assert inserted == 1
        with repo._connect() as conn:  # noqa: SLF001
            row = conn.execute(
                "SELECT draft_version, critic_item_id, original_text, "
                "revision_type, pragmatist_verdict, pragmatist_score "
                "FROM build_response_provenance LIMIT 1"
            ).fetchone()
        assert row["draft_version"] == 0
        assert row["critic_item_id"] == ""
        assert row["original_text"] == ""
        assert row["revision_type"] == "conservative"
        assert row["pragmatist_verdict"] is None
        assert row["pragmatist_score"] is None

    def test_empty_list_inserts_nothing(self, repo: BlueprintRepository) -> None:
        """Empty input list returns 0 and creates no rows."""
        inserted = repo.save_provenance_batch("sess-1", "wf-1", [])
        assert inserted == 0
        with repo._connect() as conn:  # noqa: SLF001
            count = conn.execute("SELECT COUNT(*) AS c FROM build_response_provenance").fetchone()
        assert count["c"] == 0

    def test_session_id_persisted(self, repo: BlueprintRepository) -> None:
        """The session_id column is populated from the parameter."""
        repo.save_provenance_batch(
            "session-xyz",
            "wf-1",
            [{"response_to": "r-1", "provenance": {"draft_version": 1}}],
        )
        with repo._connect() as conn:  # noqa: SLF001
            row = conn.execute("SELECT session_id, workflow_id FROM build_response_provenance LIMIT 1").fetchone()
        assert row["session_id"] == "session-xyz"
        assert row["workflow_id"] == "wf-1"


class TestPragmatistNodeUsesRepository:
    """Verify the production code path no longer hardcodes a DB path."""

    def test_pragmatist_module_no_hardcoded_db_path(self) -> None:
        """The pragmatist_nodes module must not contain any
        ``Path("data/blueprints.db")`` literal — that was the H5 bug.
        """
        from pathlib import Path

        src = (Path(__file__).resolve().parents[2] / "backend" / "workflow" / "nodes" / "pragmatist_nodes.py").read_text(encoding="utf-8")
        assert 'Path("data/blueprints.db")' not in src
        assert 'Path("data/blueprints.db")' not in src

    def test_pragmatist_module_uses_repository(self) -> None:
        """The refactored function must instantiate BlueprintRepository."""
        from pathlib import Path

        src = (Path(__file__).resolve().parents[2] / "backend" / "workflow" / "nodes" / "pragmatist_nodes.py").read_text(encoding="utf-8")
        assert "BlueprintRepository" in src
        assert "save_provenance_batch" in src
