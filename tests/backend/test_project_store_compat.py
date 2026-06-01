"""Tests for ProjectStore compatibility after path migration to tenant/case structure.

Verifies that ProjectStore correctly resolves paths under the new
``data/tenants/{tid}/cases/{cid}/`` structure while maintaining backward
compatibility with existing callers.
"""

from __future__ import annotations

import json

import pytest

from backend.persistence.project_store import ProjectStore


@pytest.fixture()
def base_dir(tmp_path):
    return tmp_path / "data"


@pytest.fixture()
def store(base_dir):
    return ProjectStore(base_dir=base_dir)


class TestProjectStorePaths:
    """Verify ProjectStore resolves paths under tenant/case structure."""

    def test_get_project_dir_returns_tenant_case_path(self, store, base_dir):
        """get_project_dir should return base_dir/{tid}/cases/{pid}/."""
        project = store.create("Test Project", tenant_id="tenant-1")
        project_dir = store.get_project_dir(project.id)
        assert "tenant-1" in str(project_dir)
        assert "cases" in str(project_dir)
        assert project.id in str(project_dir)

    def test_create_stores_in_tenant_path(self, store, base_dir):
        """Created project should be stored under {base_dir}/{tid}/cases/."""
        project = store.create("Test", tenant_id="t1")
        expected = base_dir / "t1" / "cases" / project.id
        assert expected.exists()
        assert (expected / "project.json").exists()

    def test_list_by_tenant_returns_correct_projects(self, store):
        """list_by_tenant should only return projects for the specified tenant."""
        store.create("P1", tenant_id="t1")
        store.create("P2", tenant_id="t1")
        store.create("P3", tenant_id="t2")

        t1_projects = store.list_by_tenant("t1")
        t2_projects = store.list_by_tenant("t2")

        assert len(t1_projects) == 2
        assert len(t2_projects) == 1
        assert all(p.tenant_id == "t1" for p in t1_projects)

    def test_get_returns_project_from_tenant_path(self, store):
        """get() should find a project stored under tenant/cases/."""
        project = store.create("Findable", tenant_id="t1")
        found = store.get(project.id)
        assert found is not None
        assert found.name == "Findable"
        assert found.tenant_id == "t1"

    def test_update_persists_to_tenant_path(self, store, base_dir):
        """update() should persist changes in the tenant/cases/ path."""
        project = store.create("Old Name", tenant_id="t1")
        store.update(project.id, name="New Name")

        # Re-read from disk
        json_path = base_dir / "t1" / "cases" / project.id / "project.json"
        data = json.loads(json_path.read_text())
        assert data["name"] == "New Name"

    def test_delete_removes_from_tenant_path(self, store, base_dir):
        """delete() should remove the project from tenant/cases/."""
        project = store.create("Deletable", tenant_id="t1")
        project_dir = base_dir / "t1" / "cases" / project.id
        assert project_dir.exists()

        store.delete(project.id)
        assert not project_dir.exists()

    def test_default_project_in_default_tenant(self, store):
        """Default project should be created under _default tenant."""
        default = store.get_or_create_default()
        assert default.tenant_id == "_default"
        project_dir = store.get_project_dir(default.id)
        assert "_default" in str(project_dir)

    def test_multiple_tenants_isolated(self, store):
        """Projects in different tenants should be fully isolated."""
        store.create("P1", tenant_id="alpha")
        store.create("P2", tenant_id="beta")

        # Same name, different tenants
        store.create("Shared Name", tenant_id="alpha")
        store.create("Shared Name", tenant_id="beta")

        alpha_projects = store.list_by_tenant("alpha")
        beta_projects = store.list_by_tenant("beta")

        assert len(alpha_projects) == 2
        assert len(beta_projects) == 2
        assert all(p.tenant_id == "alpha" for p in alpha_projects)
        assert all(p.tenant_id == "beta" for p in beta_projects)
