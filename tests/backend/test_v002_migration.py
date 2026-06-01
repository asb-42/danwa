"""Tests for v002 case-path migration."""

from __future__ import annotations

import json
from pathlib import Path

from backend.migrations.v002_case_pfade import _resolve_tenant_id, migrate_to_case_paths


def _create_old_project(base: Path, project_id: str, tenant_id: str = "_default", extra_dirs: list[str] | None = None) -> Path:
    """Simulate an old-style project at ``base/projects/{project_id}/``."""
    project_dir = base / "projects" / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text(
        json.dumps(
            {
                "id": project_id,
                "name": project_id.title(),
                "tenant_id": tenant_id,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    if extra_dirs:
        for d in extra_dirs:
            (project_dir / d).mkdir(parents=True, exist_ok=True)
            (project_dir / d / "test.txt").write_text("content", encoding="utf-8")
    return project_dir


class TestResolveTenantId:
    def test_from_file(self, tmp_path):
        _create_old_project(tmp_path, "p1", tenant_id="acme")
        assert _resolve_tenant_id(tmp_path / "projects" / "p1", "p1") == "acme"

    def test_default_when_field_missing(self, tmp_path):
        _create_old_project(tmp_path, "p2", tenant_id="")
        assert _resolve_tenant_id(tmp_path / "projects" / "p2", "p2") == "_default"

    def test_default_when_no_project_json(self, tmp_path):
        d = tmp_path / "projects" / "p3"
        d.mkdir(parents=True)
        assert _resolve_tenant_id(d, "p3") == "_default"

    def test_default_when_invalid_json(self, tmp_path):
        d = tmp_path / "projects" / "p4"
        d.mkdir(parents=True)
        (d / "project.json").write_text("{invalid", encoding="utf-8")
        assert _resolve_tenant_id(d, "p4") == "_default"


class TestMigrateToCasePaths:
    def test_moves_projects_to_tenant_cased_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.migrations.v002_case_pfade._DATA_DIR", tmp_path)
        monkeypatch.setattr("backend.migrations.v002_case_pfade._OLD_PROJECTS_DIR", tmp_path / "projects")

        _create_old_project(tmp_path, "p1", tenant_id="acme")
        _create_old_project(tmp_path, "p2", tenant_id="_default")

        migrate_to_case_paths()

        assert (tmp_path / "tenants" / "acme" / "cases" / "p1" / "project.json").exists()
        assert (tmp_path / "tenants" / "_default" / "cases" / "p2" / "project.json").exists()
        assert not (tmp_path / "projects" / "p1").exists()
        assert not (tmp_path / "projects" / "p2").exists()

    def test_creates_marker_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.migrations.v002_case_pfade._DATA_DIR", tmp_path)
        monkeypatch.setattr("backend.migrations.v002_case_pfade._OLD_PROJECTS_DIR", tmp_path / "projects")

        _create_old_project(tmp_path, "p1")

        migrate_to_case_paths()

        marker = tmp_path / "projects" / ".moved_to_tenant_cases"
        assert marker.exists()
        data = json.loads(marker.read_text(encoding="utf-8"))
        assert data["projects_moved"] >= 1

    def test_is_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.migrations.v002_case_pfade._DATA_DIR", tmp_path)
        monkeypatch.setattr("backend.migrations.v002_case_pfade._OLD_PROJECTS_DIR", tmp_path / "projects")

        _create_old_project(tmp_path, "p1")

        migrate_to_case_paths()
        migrate_to_case_paths()
        # Second run should not fail
        assert (tmp_path / "tenants" / "_default" / "cases" / "p1" / "project.json").exists()

    def test_moves_subdirectories(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.migrations.v002_case_pfade._DATA_DIR", tmp_path)
        monkeypatch.setattr("backend.migrations.v002_case_pfade._OLD_PROJECTS_DIR", tmp_path / "projects")

        _create_old_project(tmp_path, "p1", extra_dirs=["debates", "dms"])

        migrate_to_case_paths()

        dest = tmp_path / "tenants" / "_default" / "cases" / "p1"
        assert (dest / "debates" / "test.txt").exists()
        assert (dest / "dms" / "test.txt").exists()

    def test_skips_when_no_projects_directory(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.migrations.v002_case_pfade._DATA_DIR", tmp_path)
        monkeypatch.setattr("backend.migrations.v002_case_pfade._OLD_PROJECTS_DIR", tmp_path / "projects")

        # No projects directory at all
        migrate_to_case_paths()  # Should not raise

    def test_merges_when_target_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.migrations.v002_case_pfade._DATA_DIR", tmp_path)
        monkeypatch.setattr("backend.migrations.v002_case_pfade._OLD_PROJECTS_DIR", tmp_path / "projects")

        _create_old_project(tmp_path, "p1", extra_dirs=["debates"])
        # Pre-create target with same structure but different content
        target = tmp_path / "tenants" / "_default" / "cases" / "p1"
        (target / "debates").mkdir(parents=True)
        (target / "debates" / "existing.txt").write_text("existing", encoding="utf-8")
        (target / "project.json").write_text(
            json.dumps({"id": "p1", "name": "Existing"}),
        )

        migrate_to_case_paths()

        # Old source should be gone
        assert not (tmp_path / "projects" / "p1").exists()
        # Target should have both old and new content
        assert (target / "debates" / "existing.txt").exists()
        assert (target / "debates" / "test.txt").exists()

    def test_handles_multiple_tenants(self, tmp_path, monkeypatch):
        monkeypatch.setattr("backend.migrations.v002_case_pfade._DATA_DIR", tmp_path)
        monkeypatch.setattr("backend.migrations.v002_case_pfade._OLD_PROJECTS_DIR", tmp_path / "projects")

        _create_old_project(tmp_path, "p1", tenant_id="acme")
        _create_old_project(tmp_path, "p2", tenant_id="beta")
        _create_old_project(tmp_path, "p3", tenant_id="_default")

        migrate_to_case_paths()

        for tid in ("acme", "beta", "_default"):
            assert (tmp_path / "tenants" / tid / "cases").is_dir()
        assert (tmp_path / "tenants" / "acme" / "cases" / "p1" / "project.json").exists()
        assert (tmp_path / "tenants" / "beta" / "cases" / "p2" / "project.json").exists()
        assert (tmp_path / "tenants" / "_default" / "cases" / "p3" / "project.json").exists()
