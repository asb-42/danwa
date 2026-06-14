"""Tests for backend/blueprints/bundle_io.py — bundle export/import.

The module had 0 % coverage. These tests exercise the public surface
(``export_bundle`` and ``import_bundle``) plus the conflict-resolution
strategies (SKIP, OVERWRITE, RENAME) and the documented error paths.
"""

from __future__ import annotations

from datetime import UTC

import pytest

from backend.blueprints.bundle_io import (
    BUNDLE_EXPORT_VERSION,
    ImportConflictStrategy,
    export_bundle,
    import_bundle,
)
from backend.blueprints.models import (
    AgentBundle,
    BlueprintLLMProfile,
    RoleType,
    ToneProfile,
)
from backend.blueprints.repository import BlueprintRepository

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


def _llm_profile(pid: str = "llm-1", name: str = "Test LLM") -> BlueprintLLMProfile:
    return BlueprintLLMProfile(
        id=pid,
        name=name,
        profile_type="text",
        provider="openrouter",
        model="anthropic/claude-3.5-sonnet",
    )


def _tone_profile(tid: str = "tp-formal") -> ToneProfile:
    return ToneProfile(id=tid, name="Formal", style="neutral")


def _bundle(
    bid: str = "b-1",
    name: str = "Test Bundle",
    llm_id: str = "llm-1",
    role_id: str = "rt-critic",
    tone_id: str | None = "tp-formal",
) -> AgentBundle:
    return AgentBundle(
        id=bid,
        name=name,
        description="Round-trip test bundle",
        llm_profile_id=llm_id,
        role_type_id=role_id,
        tone_profile_id=tone_id,
        tags=["test"],
    )


@pytest.fixture()
def repo(tmp_path):
    return BlueprintRepository(db_path=tmp_path / "blueprints.db")


@pytest.fixture()
def seeded_repo(repo):
    repo.save_llm_profile(_llm_profile())
    repo.save_tone_profile(_tone_profile())
    repo.save_bundle(_bundle())
    return repo


@pytest.fixture(autouse=True)
def _stub_resolve_role_type(monkeypatch):
    """Stub the module-sourced resolver so tests are hermetic."""
    from backend.blueprints import bundle_io

    def _resolve(rid: str):
        if rid == "rt-critic":
            return RoleType(id=rid, name="Critic", category="functional")
        return None

    monkeypatch.setattr(bundle_io, "resolve_role_type", _resolve)


# ---------------------------------------------------------------------------
# export_bundle
# ---------------------------------------------------------------------------


class TestExportBundle:
    def test_export_round_trip_shape(self, seeded_repo):
        data = export_bundle("b-1", seeded_repo)

        assert data["export_version"] == BUNDLE_EXPORT_VERSION
        assert data["type"] == "agent_bundle"
        assert "exported_at" in data
        # Bundle payload
        assert data["bundle"]["id"] == "b-1"
        assert data["bundle"]["name"] == "Test Bundle"
        # LLM profile payload
        assert data["llm_profile"]["id"] == "llm-1"
        assert data["llm_profile"]["provider"] == "openrouter"
        # Role type payload
        assert data["role_type"]["id"] == "rt-critic"
        # Tone profile payload
        assert data["tone_profile"] is not None
        assert data["tone_profile"]["id"] == "tp-formal"

    def test_export_missing_bundle_raises(self, seeded_repo):
        with pytest.raises(ValueError, match="Bundle 'nope' not found"):
            export_bundle("nope", seeded_repo)

    def test_export_missing_llm_profile_raises(self, repo):
        # Insert a bundle that references a non-existent LLM profile by
        # bypassing FK enforcement.  ``export_bundle`` must still refuse
        # to produce an inconsistent export.
        import json as _json
        import sqlite3
        from datetime import datetime

        conn = sqlite3.connect(str(repo.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=OFF")
        now = datetime.now(UTC).isoformat()
        conn.execute(
            """
            INSERT INTO agent_bundles (
                id, name, description, llm_profile_id, role_type_id,
                tone_profile_id, tags_json, is_active, created_at,
                updated_at, composition_json, model_params_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "b-1",
                "Test Bundle",
                "Round-trip test bundle",
                "llm-missing",  # FK target is intentionally absent
                "rt-critic",
                None,
                _json.dumps(["test"]),
                1,
                now,
                now,
                "{}",
                "{}",
            ),
        )
        conn.commit()
        conn.close()

        with pytest.raises(ValueError, match="Referenced LLM profile"):
            export_bundle("b-1", repo)

    def test_export_missing_role_type_raises(self, seeded_repo, monkeypatch):
        from backend.blueprints import bundle_io

        monkeypatch.setattr(bundle_io, "resolve_role_type", lambda _r: None)
        with pytest.raises(ValueError, match="Referenced RoleType"):
            export_bundle("b-1", seeded_repo)

    def test_export_without_tone_profile(self, repo):
        """If the bundle has no tone profile, the export sets tone_profile=None."""
        repo.save_llm_profile(_llm_profile())
        repo.save_bundle(_bundle(tone_id=None))

        data = export_bundle("b-1", repo)
        assert data["tone_profile"] is None
        assert data["bundle"]["tone_profile_id"] is None


# ---------------------------------------------------------------------------
# import_bundle — error paths
# ---------------------------------------------------------------------------


class TestImportBundleErrors:
    def test_wrong_type_raises(self, seeded_repo):
        with pytest.raises(ValueError, match="Expected type 'agent_bundle'"):
            import_bundle({"type": "other"}, seeded_repo)

    def test_missing_bundle_key_raises(self, seeded_repo):
        with pytest.raises(ValueError, match="Missing 'bundle' key"):
            import_bundle({"type": "agent_bundle"}, seeded_repo)

    def test_missing_role_type_raises(self, seeded_repo):
        data = {
            "type": "agent_bundle",
            "bundle": {"id": "x", "name": "X", "llm_profile_id": "llm-1"},
            "llm_profile": {
                "id": "llm-1",
                "name": "L",
                "provider": "openrouter",
                "model": "m",
            },
            # role_type omitted
        }
        with pytest.raises(ValueError, match="Missing 'role_type'"):
            import_bundle(data, seeded_repo)

    def test_missing_llm_profile_raises(self, seeded_repo):
        data = {
            "type": "agent_bundle",
            "bundle": {"id": "x", "name": "X", "llm_profile_id": "llm-1"},
            "role_type": {"id": "rt-critic"},
            # llm_profile omitted
        }
        with pytest.raises(ValueError, match="Missing 'llm_profile'"):
            import_bundle(data, seeded_repo)


# ---------------------------------------------------------------------------
# import_bundle — RENAME (default)
# ---------------------------------------------------------------------------


class TestImportBundleRename:
    def test_rename_creates_new_bundle_id(self, seeded_repo):
        data = export_bundle("b-1", seeded_repo)
        new_bundle = import_bundle(data, seeded_repo)

        assert new_bundle.id != "b-1"
        assert new_bundle.id.startswith("b-1_")
        # The original bundle must still be there, untouched
        assert seeded_repo.get_bundle("b-1") is not None

    def test_rename_creates_new_llm_profile(self, seeded_repo):
        data = export_bundle("b-1", seeded_repo)
        new_bundle = import_bundle(data, seeded_repo)

        # Original LLM profile is preserved
        assert seeded_repo.get_llm_profile("llm-1") is not None
        # New LLM profile exists under the renamed id
        renamed = seeded_repo.get_llm_profile(new_bundle.llm_profile_id)
        assert renamed is not None
        assert renamed.id != "llm-1"
        assert renamed.id.startswith("llm-1_")

    def test_rename_preserves_references(self, seeded_repo):
        data = export_bundle("b-1", seeded_repo)
        new_bundle = import_bundle(data, seeded_repo)

        # Cross-references point to the NEW entities, not the originals
        assert new_bundle.llm_profile_id.startswith("llm-1_")
        # Role type is module-sourced, not renamed
        assert new_bundle.role_type_id == "rt-critic"
        # Tone profile was renamed
        assert new_bundle.tone_profile_id is not None
        assert new_bundle.tone_profile_id.startswith("tp-formal_")
        assert seeded_repo.get_tone_profile(new_bundle.tone_profile_id) is not None


# ---------------------------------------------------------------------------
# import_bundle — SKIP / OVERWRITE
# ---------------------------------------------------------------------------


class TestImportBundleSkip:
    def test_skip_returns_existing(self, seeded_repo):
        data = export_bundle("b-1", seeded_repo)
        result = import_bundle(data, seeded_repo, conflict_strategy=ImportConflictStrategy.SKIP)
        # No new entity created; the original is returned
        assert result.id == "b-1"


class TestImportBundleOverwrite:
    def test_overwrite_replaces_name(self, seeded_repo):
        data = export_bundle("b-1", seeded_repo)
        data["bundle"]["name"] = "Renamed Bundle"
        data["llm_profile"]["name"] = "Renamed LLM"

        result = import_bundle(data, seeded_repo, conflict_strategy=ImportConflictStrategy.OVERWRITE)
        assert result.id == "b-1"
        assert result.name == "Renamed Bundle"

        # LLM profile is overwritten in place
        llm = seeded_repo.get_llm_profile("llm-1")
        assert llm is not None
        assert llm.name == "Renamed LLM"


# ---------------------------------------------------------------------------
# Cross-repo round-trip
# ---------------------------------------------------------------------------


class TestBundleRoundTrip:
    def test_export_import_into_empty_repo(self, seeded_repo, tmp_path):
        exported = export_bundle("b-1", seeded_repo)
        target = BlueprintRepository(db_path=tmp_path / "target.db")

        result = import_bundle(exported, target)

        assert result.name == "Test Bundle"
        # All referenced entities live in the target DB now
        assert target.get_llm_profile(result.llm_profile_id) is not None
        assert target.get_tone_profile(result.tone_profile_id) is not None

    def test_export_import_skip_into_empty_repo(self, seeded_repo, tmp_path):
        exported = export_bundle("b-1", seeded_repo)
        target = BlueprintRepository(db_path=tmp_path / "target_skip.db")

        result = import_bundle(exported, target, conflict_strategy=ImportConflictStrategy.SKIP)
        # First import into an empty repo: SKIP has no effect, IDs preserved
        assert result.id == "b-1"
        assert target.get_llm_profile("llm-1") is not None
