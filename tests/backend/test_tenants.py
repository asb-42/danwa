"""Tests for tenant model, TenantStore, and tenant isolation."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from backend.models.tenant import Tenant
from backend.persistence.tenant_store import TenantStore


class TestTenantStore:
    def _make_store(self):
        tmpdir = tempfile.mkdtemp()
        return TenantStore(db_path=Path(tmpdir) / "test_auth.db")

    def test_create_and_get(self):
        store = self._make_store()
        tenant = store.create("Acme Corp", plan="pro")
        assert tenant.name == "Acme Corp"
        assert tenant.plan == "pro"
        assert tenant.is_active is True

        fetched = store.get(tenant.id)
        assert fetched is not None
        assert fetched.name == "Acme Corp"

    def test_create_with_custom_id(self):
        store = self._make_store()
        tenant = store.create("Default", tenant_id="_default")
        assert tenant.id == "_default"

    def test_list_all(self):
        store = self._make_store()
        store.create("A")
        store.create("B")
        store.create("C")
        assert len(store.list_all()) == 3

    def test_update(self):
        store = self._make_store()
        tenant = store.create("Old Name")
        updated = store.update(tenant.id, name="New Name", plan="enterprise")
        assert updated.name == "New Name"
        assert updated.plan == "enterprise"

    def test_update_settings(self):
        store = self._make_store()
        tenant = store.create("T")
        updated = store.update(tenant.id, settings={"tts_engine": "pyttsx3"})
        assert updated.settings == {"tts_engine": "pyttsx3"}

    def test_delete(self):
        store = self._make_store()
        tenant = store.create("D")
        assert store.get(tenant.id) is not None
        store.delete(tenant.id)
        assert store.get(tenant.id) is None

    def test_count(self):
        store = self._make_store()
        assert store.count() == 0
        store.create("A")
        assert store.count() == 1
        store.create("B")
        assert store.count() == 2


class TestTenantModel:
    def test_default_values(self):
        t = Tenant(name="Test")
        assert t.plan == "free"
        assert t.max_projects == 5
        assert t.max_concurrent_debates == 2
        assert t.max_documents == 50
        assert t.is_active is True

    def test_custom_values(self):
        t = Tenant(name="Pro", plan="pro", max_projects=50, max_documents=500)
        assert t.plan == "pro"
        assert t.max_projects == 50
        assert t.max_documents == 500


class TestProjectTenantScoping:
    """Test that projects are properly scoped to tenants."""

    def test_project_has_tenant_id(self):
        from backend.models.project import Project

        p = Project(name="Test", tenant_id="tenant-1")
        assert p.tenant_id == "tenant-1"

    def test_project_default_tenant_id(self):
        from backend.models.project import Project

        p = Project(name="Test")
        assert p.tenant_id == "_default"

    def test_project_store_list_by_tenant(self):
        from backend.persistence.project_store import ProjectStore

        tmpdir = tempfile.mkdtemp()
        store = ProjectStore(base_dir=Path(tmpdir) / "projects")

        store.create("P1", tenant_id="t1")
        store.create("P2", tenant_id="t1")
        store.create("P3", tenant_id="t2")

        assert len(store.list_by_tenant("t1")) == 2
        assert len(store.list_by_tenant("t2")) == 1
        assert len(store.list_by_tenant("t3")) == 0


class TestQuotaChecks:
    """Test quota enforcement functions."""

    def test_debate_quota_pass(self):
        from backend.api.quota import check_debate_quota

        t = Tenant(name="T", max_concurrent_debates=2)
        check_debate_quota(t, 1)  # Should not raise

    def test_debate_quota_fail(self):
        from backend.api.quota import check_debate_quota

        t = Tenant(name="T", max_concurrent_debates=2)
        with pytest.raises(Exception):  # HTTPException
            check_debate_quota(t, 2)

    def test_document_quota_pass(self):
        from backend.api.quota import check_document_quota

        t = Tenant(name="T", max_documents=50)
        check_document_quota(t, 49)

    def test_document_quota_fail(self):
        from backend.api.quota import check_document_quota

        t = Tenant(name="T", max_documents=50)
        with pytest.raises(Exception):
            check_document_quota(t, 50)

    def test_project_quota_pass(self):
        from backend.api.quota import check_project_quota

        t = Tenant(name="T", max_projects=5)
        check_project_quota(t, 4)

    def test_project_quota_fail(self):
        from backend.api.quota import check_project_quota

        t = Tenant(name="T", max_projects=5)
        with pytest.raises(Exception):
            check_project_quota(t, 5)
