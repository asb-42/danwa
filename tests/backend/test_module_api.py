"""Tests for Module API endpoints (REST router)."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.routers.modules import get_module_service
from backend.main import create_app

TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="test_api_db_"))
TEST_MODULES_DIR = Path(tempfile.mkdtemp(prefix="test_api_modules_"))


def _make_module(modules_dir: Path, module_id: str, version: str = "1.0.0") -> dict:
    """Create a minimal module directory with manifest and files."""
    import hashlib

    mod_dir = modules_dir / module_id
    mod_dir.mkdir(parents=True, exist_ok=True)

    content = f"# {module_id}\n\nTest content."
    chksum = hashlib.sha256(content.encode()).hexdigest()
    (mod_dir / "readme.md").write_text(content)

    manifest = {
        "schema_version": "1.0.0",
        "module_id": module_id,
        "name": {"en": f"{module_id} name"},
        "description": {"en": "Test module"},
        "version": version,
        "type": "argumentation-pattern",
        "category": "prompts",
        "author": {"name": "Test"},
        "license": "CC-BY-4.0",
        "checksum": hashlib.sha256(
            json.dumps([{"path": "readme.md", "format": "markdown", "checksum": chksum, "language": "en"}]).encode()
        ).hexdigest(),
        "files": [
            {"path": "readme.md", "format": "markdown", "checksum": chksum, "language": "en"},
        ],
    }

    (mod_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


@pytest.fixture(autouse=True)
def clean_env():
    """Clean up before and after each test."""
    global _module_service
    _module_service = None

    for d in [TEST_MODULES_DIR, TEST_DB_DIR]:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    TEST_MODULES_DIR.mkdir(parents=True, exist_ok=True)
    TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
    yield
    for d in [TEST_MODULES_DIR, TEST_DB_DIR]:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)

    # Reset module router function
    import backend.api.routers.modules as mod_router

    mod_router.get_module_service = get_module_service


def _make_app_with_service():
    """Helper: create app with overridden module service."""
    from backend.modules.service import ModuleService

    test_service = ModuleService(
        modules_dir=TEST_MODULES_DIR,
        db_path=TEST_DB_DIR / "test.db",
    )

    # Patch the getter in the router module to return our test service
    import backend.api.routers.modules as mod_router

    # Use a closure so the lambda captures test_service
    mod_router.get_module_service = lambda svc=test_service: svc

    # Also set the module-level singleton
    mod_router._module_service = test_service

    application = create_app()
    client = TestClient(application)

    # Do NOT restore here - let the clean_env fixture handle cleanup
    # The lambda stays in place for the lifetime of the test

    return client, test_service


class TestListModules:
    """GET /api/v1/modules/"""

    def test_empty_list(self):
        client, _ = _make_app_with_service()
        response = client.get("/api/v1/modules/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_with_modules(self):
        client, svc = _make_app_with_service()
        _make_module(TEST_MODULES_DIR, "danwa-test-1", version="1.0.0")

        # Need to install via installer since service.install looks in modules_dir
        from backend.modules.installer import ModuleInstaller

        ModuleInstaller(TEST_MODULES_DIR, svc.db_path)

        # Remove the module dir so install finds it fresh from modules_dir
        # Actually, service.install reads from modules_dir, which is where it already is
        # So just call service.install - it will skip because source==target same version
        # For this test, let's verify it shows up in listing

        response = client.get("/api/v1/modules/")
        assert response.status_code == 200
        data = response.json()
        module_ids = [m["module_id"] for m in data]
        assert "danwa-test-1" in module_ids

    def test_list_available(self):
        client, _ = _make_app_with_service()
        response = client.get("/api/v1/modules/available")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Endpoint currently returns empty list (remote registry not yet implemented)
        # Local modules are served via GET /api/v1/modules/ instead


class TestGetModule:
    """GET /api/v1/modules/{module_id}"""

    def test_get_existing(self):
        client, svc = _make_app_with_service()
        _make_module(TEST_MODULES_DIR, "danwa-test-get", version="1.2.3")

        response = client.get("/api/v1/modules/danwa-test-get")
        assert response.status_code == 200
        data = response.json()
        assert data["module_id"] == "danwa-test-get"
        assert data["version"] == "1.2.3"

    def test_get_nonexistent(self):
        client, _ = _make_app_with_service()
        response = client.get("/api/v1/modules/nonexistent-module")
        assert response.status_code == 404


class TestInstallModule:
    """POST /api/v1/modules/install"""

    def test_install_success(self):
        """Install a module that exists in modules_dir but not yet in DB."""
        # This test creates a module with version 1.0.0 in modules_dir,
        # but the install endpoint looks for it there and installs to DB.
        # Since no prior DB entry exists, it will install (not skip).
        client, _ = _make_app_with_service()

        # Create a module in a temp dir, then move to a known location
        # The API's install_from_directory reads from modules_dir/module_id
        _make_module(TEST_MODULES_DIR, "danwa-install-test", version="1.0.0")

        response = client.post(
            "/api/v1/modules/install",
            json={
                "module_id": "danwa-install-test",
                "source": "local",
            },
        )
        # Should succeed since module exists in modules_dir and isn't in DB yet
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "ok"
        assert data["module_id"] == "danwa-install-test"

    def test_install_not_found(self):
        client, _ = _make_app_with_service()
        response = client.post(
            "/api/v1/modules/install",
            json={
                "module_id": "nonexistent-module",
                "source": "local",
            },
        )
        assert response.status_code == 404

    def test_install_already_installed(self):
        """Installing already-registered module returns skipped."""
        client, _ = _make_app_with_service()
        _make_module(TEST_MODULES_DIR, "danwa-dup", version="1.0.0")

        # First install
        response = client.post(
            "/api/v1/modules/install",
            json={
                "module_id": "danwa-dup",
                "source": "local",
            },
        )
        assert response.status_code == 201

        # Second install -> skipped
        response = client.post(
            "/api/v1/modules/install",
            json={
                "module_id": "danwa-dup",
                "source": "local",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "skipped"


class TestUninstallModule:
    """POST /api/v1/modules/{module_id}/uninstall"""

    def test_uninstall_success(self):
        client, _ = _make_app_with_service()
        _make_module(TEST_MODULES_DIR, "danwa-uninstall-test", version="1.0.0")

        # First install
        client.post(
            "/api/v1/modules/install",
            json={
                "module_id": "danwa-uninstall-test",
                "source": "local",
            },
        )

        response = client.post(
            "/api/v1/modules/danwa-uninstall-test/uninstall",
            json={
                "force": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_uninstall_nonexistent(self):
        client, _ = _make_app_with_service()
        response = client.post(
            "/api/v1/modules/nonexistent/uninstall",
            json={
                "force": False,
            },
        )
        assert response.status_code == 200


class TestUpdateModule:
    """PUT /api/v1/modules/{module_id}/update"""

    def test_update_success(self):
        client, _ = _make_app_with_service()

        # Create v1.0.0 and install
        _make_module(TEST_MODULES_DIR, "danwa-update-test", version="1.0.0")
        client.post(
            "/api/v1/modules/install",
            json={
                "module_id": "danwa-update-test",
                "source": "local",
            },
        )

        # Overwrite with v2.0.0
        _make_module(TEST_MODULES_DIR, "danwa-update-test", version="2.0.0")
        response = client.put("/api/v1/modules/danwa-update-test/update")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "2.0.0"

    def test_update_nonexistent(self):
        client, _ = _make_app_with_service()
        response = client.put("/api/v1/modules/nonexistent/update")
        assert response.status_code == 404


class TestValidateModule:
    """POST /api/v1/modules/validate"""

    def test_valid_manifest(self):
        client, _ = _make_app_with_service()
        response = client.post(
            "/api/v1/modules/validate",
            json={
                "manifest": {
                    "schema_version": "1.0.0",
                    "module_id": "danwa-valid-test",
                    "name": {"en": "Test"},
                    "description": {"en": "Test desc"},
                    "version": "1.0.0",
                    "type": "argumentation-pattern",
                    "category": "prompts",
                    "files": [{"path": "test.md", "format": "markdown", "checksum": "abc", "language": "en"}],
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True

    def test_invalid_manifest_missing_fields(self):
        client, _ = _make_app_with_service()
        response = client.post(
            "/api/v1/modules/validate",
            json={
                "manifest": {
                    "module_id": "danwa-invalid",
                }
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["issues"]) > 0


class TestTranslateModule:
    """POST /api/v1/translation/{module_id}/translate"""

    def test_translate_success(self):
        client, _ = _make_app_with_service()
        _make_module(TEST_MODULES_DIR, "danwa-translate-test", version="1.0.0")
        client.post(
            "/api/v1/modules/install",
            json={
                "module_id": "danwa-translate-test",
                "source": "local",
            },
        )

        response = client.post(
            "/api/v1/translation/danwa-translate-test/translate",
            json={
                "target_language": "de",
                "force": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["module_id"] == "danwa-translate-test"
        assert data["target_language"] == "de"


class TestTranslationStatus:
    """GET /api/v1/translation/{module_id}/status"""

    def test_translation_status(self):
        client, _ = _make_app_with_service()
        _make_module(TEST_MODULES_DIR, "danwa-trans-status", version="1.0.0")
        client.post(
            "/api/v1/modules/install",
            json={
                "module_id": "danwa-trans-status",
                "source": "local",
            },
        )
        client.post(
            "/api/v1/translation/danwa-trans-status/translate",
            json={
                "target_language": "de",
            },
        )

        response = client.get("/api/v1/translation/danwa-trans-status/status")
        assert response.status_code == 200
        data = response.json()
        assert "module_id" in data
        assert "translations" in data
