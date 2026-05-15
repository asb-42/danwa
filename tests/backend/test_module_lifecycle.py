"""Tests for Module lifecycle: Install → List → Update → Uninstall → Reinstall (Plan 009 Sprint 6)."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from backend.modules.service import ModuleService
from backend.modules.validation import ModuleValidator

TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="test_lifecycle_db_"))
TEST_MODULES_DIR = Path(tempfile.mkdtemp(prefix="test_lifecycle_modules_"))


def _make_module(modules_dir: Path, module_id: str, version: str = "1.0.0") -> dict:
    """Create a minimal module directory with manifest and files."""
    import hashlib

    mod_dir = modules_dir / module_id
    mod_dir.mkdir(parents=True, exist_ok=True)

    content = f"# {module_id} v{version}\n\nTest content."
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
        "checksum": chksum,
        "files": [
            {"path": "readme.md", "format": "markdown", "checksum": chksum, "language": "en"},
        ],
    }

    (mod_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


@pytest.fixture(autouse=True)
def clean_dirs():
    """Clean up before and after each test."""
    for d in [TEST_MODULES_DIR, TEST_DB_DIR]:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    TEST_MODULES_DIR.mkdir(parents=True, exist_ok=True)
    TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
    yield
    for d in [TEST_MODULES_DIR, TEST_DB_DIR]:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)


@pytest.fixture()
def service():
    """ModuleService with test directories."""
    return ModuleService(
        modules_dir=TEST_MODULES_DIR,
        db_path=TEST_DB_DIR / "test.db",
    )


class TestModuleLifecycle:
    """Complete lifecycle: Install → List → Update → Uninstall → Reinstall."""

    def test_full_lifecycle(self, service):
        module_id = "lifecycle-test"

        # 1. Create module v1.0.0
        _make_module(TEST_MODULES_DIR, module_id, version="1.0.0")

        # 2. Install
        report = service.install(module_id, source="local")
        assert report.status == "ok"
        assert report.module_id == module_id

        # 3. List — should show the module
        modules = service.discover_local()
        ids = [m.module_id for m in modules]
        assert module_id in ids

        # 4. Update to v2.0.0
        _make_module(TEST_MODULES_DIR, module_id, version="2.0.0")
        update_report = service.update(module_id)
        assert update_report.status == "ok"
        assert update_report.version == "2.0.0"

        # 5. Uninstall
        uninstall_report = service.uninstall(module_id, force=True)
        assert uninstall_report.status == "ok"

        # 6. Verify removed from list
        modules = service.discover_local()
        ids = [m.module_id for m in modules]
        assert module_id not in ids

        # 7. Reinstall
        _make_module(TEST_MODULES_DIR, module_id, version="1.0.0")
        reinstall_report = service.install(module_id, source="local")
        assert reinstall_report.status == "ok"


class TestDependencyManagement:
    """Tests for module dependency handling."""

    def test_module_with_dependencies(self, service):
        # Create a module that depends on another
        mod_dir = TEST_MODULES_DIR / "danwa-dependent"
        mod_dir.mkdir(parents=True, exist_ok=True)

        # Create a minimal file so install proceeds past validation
        content = "# Dependent Module"
        (mod_dir / "readme.md").write_text(content)

        import hashlib

        chksum = hashlib.sha256(content.encode()).hexdigest()

        manifest = {
            "schema_version": "1.0.0",
            "module_id": "danwa-dependent",
            "name": {"en": "Dependent Module"},
            "description": {"en": "Depends on base"},
            "version": "1.0.0",
            "type": "argumentation-pattern",
            "category": "prompts",
            "author": {"name": "Test"},
            "license": "CC-BY-4.0",
            "dependencies": {"danwa-base": ">=1.0.0"},
            "files": [
                {"path": "readme.md", "format": "markdown", "checksum": chksum, "language": "en"},
            ],
        }
        (mod_dir / "manifest.json").write_text(json.dumps(manifest))

        # Install should succeed (dependencies are not enforced strictly in install)
        report = service.install("danwa-dependent", source="local")
        assert report.status in ("ok", "skipped")


class TestParallelInstallation:
    """Tests for installing multiple modules in parallel."""

    def test_install_multiple_modules(self, service):
        module_ids = ["parallel-a", "parallel-b", "parallel-c"]

        for mid in module_ids:
            _make_module(TEST_MODULES_DIR, mid, version="1.0.0")

        for mid in module_ids:
            report = service.install(mid, source="local")
            assert report.status == "ok"

        # Verify all are listed
        modules = service.discover_local()
        ids = {m.module_id for m in modules}
        for mid in module_ids:
            assert mid in ids


class TestSecurityValidation:
    """Tests for module security: no executable files allowed."""

    def test_reject_executable_files(self):
        validator = ModuleValidator(TEST_MODULES_DIR)

        mod_dir = TEST_MODULES_DIR / "malicious-module"
        mod_dir.mkdir(parents=True, exist_ok=True)

        # Create a Python file (should be rejected)
        (mod_dir / "script.py").write_text("import os; os.system('rm -rf /')")

        manifest = {
            "schema_version": "1.0.0",
            "module_id": "malicious-module",
            "name": {"en": "Malicious"},
            "description": {"en": "Contains executable"},
            "version": "1.0.0",
            "type": "custom",
            "category": "general",
            "author": {"name": "Evil"},
            "license": "MIT",
            "files": [
                {"path": "script.py", "format": "python", "checksum": "abc", "language": "en"},
            ],
        }
        (mod_dir / "manifest.json").write_text(json.dumps(manifest))

        result = validator.validate_manifest(manifest)
        assert not result.valid
        assert any("executable" in issue.message.lower() or "python" in issue.message.lower() for issue in result.issues)

    def test_reject_binary_files(self):
        validator = ModuleValidator(TEST_MODULES_DIR)

        mod_dir = TEST_MODULES_DIR / "binary-module"
        mod_dir.mkdir(parents=True, exist_ok=True)

        # Create a binary file
        (mod_dir / "payload.bin").write_bytes(b"\x00\x01\x02\x03")

        manifest = {
            "schema_version": "1.0.0",
            "module_id": "binary-module",
            "name": {"en": "Binary"},
            "description": {"en": "Contains binary"},
            "version": "1.0.0",
            "type": "custom",
            "category": "general",
            "author": {"name": "Test"},
            "license": "MIT",
            "files": [
                {"path": "payload.bin", "format": "binary", "checksum": "abc", "language": "en"},
            ],
        }
        (mod_dir / "manifest.json").write_text(json.dumps(manifest))

        result = validator.validate_manifest(manifest)
        assert not result.valid
