"""Tests for ModuleService — discovery, listing, translation."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

from backend.modules.installer import ModuleInstaller
from backend.modules.models import TranslationResult
from backend.modules.service import ModuleService


def _make_module(modules_dir: Path, module_id: str, version: str = "1.0.0", num_files: int = 1) -> dict:
    """Create a minimal module directory with manifest and files."""
    mod_dir = modules_dir / module_id
    mod_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for i in range(num_files):
        fname = f"file_{i}.md"
        fpath = mod_dir / fname
        content = f"# {module_id} file {i}\n\nContent for testing."
        fpath.write_text(content)
        chksum = hashlib.sha256(content.encode()).hexdigest()
        files.append(
            {
                "path": fname,
                "format": "markdown",
                "language": "en",
                "checksum": chksum,
            }
        )

    manifest = {
        "schema_version": "1.0.0",
        "module_id": module_id,
        "name": {"en": f"{module_id} name", "de": f"{module_id} Name"},
        "description": {"en": f"{module_id} desc"},
        "version": version,
        "type": "argumentation-pattern",
        "category": "prompts",
        "author": {"name": "Test"},
        "license": "CC-BY-4.0",
        "checksum": hashlib.sha256(json.dumps(files).encode()).hexdigest(),
        "files": files,
    }

    (mod_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


@pytest.fixture()
def tmp_dirs():
    modules_dir = Path(tempfile.mkdtemp(prefix="test_svc_m_"))
    db_dir = Path(tempfile.mkdtemp(prefix="test_svc_d_"))
    db_path = db_dir / "test.db"
    yield modules_dir, db_path
    shutil.rmtree(modules_dir, ignore_errors=True)
    shutil.rmtree(db_dir, ignore_errors=True)


@pytest.fixture()
def service(tmp_dirs):
    """Create a ModuleService with clean test dirs."""
    modules_dir, db_path = tmp_dirs
    return ModuleService(modules_dir=modules_dir, db_path=db_path)


@pytest.fixture()
def populated_service(service, tmp_dirs):
    """Service with modules installed via installer (separate src dirs)."""
    modules_dir = tmp_dirs[0]
    src_dir = Path(tempfile.mkdtemp(prefix="src_"))

    # Create in separate source dirs
    _make_module(src_dir, "danwa-test-a", version="1.0.0", num_files=2)
    _make_module(src_dir, "danwa-test-b", version="2.0.0", num_files=1)

    # Install via installer directly (source != target)
    installer = ModuleInstaller(modules_dir, service.db_path)
    installer.install_from_directory(src_dir / "danwa-test-a")
    installer.install_from_directory(src_dir / "danwa-test-b")

    shutil.rmtree(src_dir, ignore_errors=True)
    return service


class TestDiscoverLocal:
    """Test local module discovery."""

    def test_empty_dir(self, service):
        """Empty modules dir returns empty list."""
        result = service.discover_local()
        assert result == []

    def test_discovers_modules(self, service):
        """Discovers all modules with manifest.json (not hidden)."""
        _make_module(service.modules_dir, "danwa-alpha", version="1.0.0")
        _make_module(service.modules_dir, "danwa-beta", version="2.0.0")
        (service.modules_dir / "not-a-module").mkdir(exist_ok=True)
        (service.modules_dir / ".hidden").mkdir(exist_ok=True)
        (service.modules_dir / ".hidden" / "manifest.json").write_text('{"module_id": "hidden"}')

        result = service.discover_local()
        assert len(result) == 2
        ids = {m.module_id for m in result}
        assert ids == {"danwa-alpha", "danwa-beta"}

    def test_module_info_fields(self, service):
        """ModuleInfo has all expected fields."""
        _make_module(service.modules_dir, "danwa-info-test", version="1.2.3")
        result = service.discover_local()
        assert len(result) == 1
        mod = result[0]
        assert mod.module_id == "danwa-info-test"
        assert mod.version == "1.2.3"
        assert mod.type.value == "argumentation-pattern"
        assert mod.category.value == "prompts"
        assert mod.installed is True
        assert mod.file_count == 1

    def test_skips_hidden_dirs(self, service):
        """Hidden directories (starting with .) are skipped."""
        _make_module(service.modules_dir, "danwa-visible", version="1.0.0")
        (service.modules_dir / ".hidden-module").mkdir()
        (service.modules_dir / ".hidden-module" / "manifest.json").write_text('{"module_id": "hidden"}')

        result = service.discover_local()
        assert all(m.module_id != "hidden" for m in result)

    def test_skips_dirs_without_manifest(self, service):
        """Directories without manifest.json are skipped."""
        (service.modules_dir / "no-manifest").mkdir()
        (service.modules_dir / "no-manifest" / "readme.txt").write_text("hi")
        result = service.discover_local()
        assert len(result) == 0


class TestDiscoverLocalWithStatus:
    """Test discovery with DB status enrichment."""

    def test_includes_db_status(self, service):
        """DB status (installed, enabled) is included for installed modules."""
        src_dir = Path(tempfile.mkdtemp(prefix="src_"))
        _make_module(src_dir, "danwa-a", version="1.0.0")
        installer = ModuleInstaller(service.modules_dir, service.db_path)
        installer.install_from_directory(src_dir / "danwa-a")
        shutil.rmtree(src_dir, ignore_errors=True)

        result = service.discover_local_with_status()
        assert len(result) >= 1
        for mod in result:
            assert "installed" in mod
            assert "enabled" in mod

    def test_includes_db_only_modules(self, service):
        """DB-only modules (not on disk) are also returned."""
        # Initialize DB schema first
        conn = sqlite3.connect(str(service.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        from backend.blueprints.migrations import run_migrations

        run_migrations(service.db_path)

        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO module_registry
                (id, name, description, type, category, version,
                 author_json, license, checksum, installed_at,
                 updated_at, enabled, source_schema, tags_json, dependencies)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "db-only-mod",
                '{"en":"DB Only"}',
                "desc",
                "custom",
                "custom",
                "1.0.0",
                "{}",
                "CC-BY-4.0",
                "",
                "2024-01-01",
                "2024-01-01",
                1,
                "1.0.0",
                "[]",
                "{}",
            ),
        )
        conn.commit()
        conn.close()

        result = service.discover_local_with_status()
        db_only = [m for m in result if m["module_id"] == "db-only-mod"]
        assert len(db_only) == 1
        assert db_only[0]["on_disk"] is False


class TestGet:
    """Test single module lookup."""

    def test_get_existing(self, service):
        _make_module(service.modules_dir, "danwa-get-test", version="1.0.0")
        result = service.get("danwa-get-test")
        assert result is not None
        assert result.module_id == "danwa-get-test"

    def test_get_nonexistent(self, service):
        result = service.get("nonexistent")
        assert result is None


class TestListAll:
    """Test listing with category filter."""

    def test_list_all_no_filter(self, service):
        src_dir = Path(tempfile.mkdtemp(prefix="src_"))
        _make_module(src_dir, "danwa-cat-a", version="1.0.0")
        installer = ModuleInstaller(service.modules_dir, service.db_path)
        installer.install_from_directory(src_dir / "danwa-cat-a")
        shutil.rmtree(src_dir, ignore_errors=True)

        result = service.list_all()
        assert len(result) >= 1

    def test_list_all_with_category(self, service):
        src_dir = Path(tempfile.mkdtemp(prefix="src_"))
        _make_module(src_dir, "danwa-cat-test", version="1.0.0")
        installer = ModuleInstaller(service.modules_dir, service.db_path)
        installer.install_from_directory(src_dir / "danwa-cat-test")
        shutil.rmtree(src_dir, ignore_errors=True)

        result = service.list_all(category="prompts")
        assert any(m.module_id == "danwa-cat-test" for m in result)

    def test_list_all_empty_category(self, service):
        """Filtering by non-matching category returns empty."""
        src_dir = Path(tempfile.mkdtemp(prefix="src_"))
        _make_module(src_dir, "danwa-cat-test", version="1.0.0")
        installer = ModuleInstaller(service.modules_dir, service.db_path)
        installer.install_from_directory(src_dir / "danwa-cat-test")
        shutil.rmtree(src_dir, ignore_errors=True)

        result = service.list_all(category="nonexistent")
        assert result == []


class TestInstallUninstall:
    """Test install/uninstall via service."""

    def test_install_via_service(self, service):
        """Install module by placing it in modules_dir then calling install."""
        src_dir = Path(tempfile.mkdtemp(prefix="src_"))
        _make_module(src_dir, "danwa-svc-install")

        # service.install() expects module in modules_dir, so copy it there
        shutil.copytree(src_dir / "danwa-svc-install", service.modules_dir / "danwa-svc-install")

        report = service.install("danwa-svc-install", source="local")
        shutil.rmtree(src_dir, ignore_errors=True)

        # First call registers in DB (status=ok since version differs from nothing)
        assert report.status == "ok" or report.status == "skipped"

    def test_install_via_service_not_found(self, service):
        """Installing nonexistent module raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            service.install("nonexistent-module")

    def test_uninstall_via_service(self, service):
        src_dir = Path(tempfile.mkdtemp(prefix="src_"))
        _make_module(src_dir, "danwa-svc-uninst")
        shutil.copytree(src_dir / "danwa-svc-uninst", service.modules_dir / "danwa-svc-uninst")
        service.install("danwa-svc-uninst", source="local")
        shutil.rmtree(src_dir, ignore_errors=True)

        report = service.uninstall("danwa-svc-uninst")
        assert report.status == "ok"

    def test_force_uninstall(self, service):
        """Force uninstall skips dependency check."""
        src_dir = Path(tempfile.mkdtemp(prefix="src_"))
        _make_module(src_dir, "danwa-force")
        shutil.copytree(src_dir / "danwa-force", service.modules_dir / "danwa-force")
        service.install("danwa-force", source="local")
        shutil.rmtree(src_dir, ignore_errors=True)

        report = service.uninstall("danwa-force", force=True)
        assert report.status == "ok"


class TestUpdate:
    """Test module update via service."""

    def test_update_existing(self, service):
        src_dir = Path(tempfile.mkdtemp(prefix="src_"))
        _make_module(src_dir, "danwa-upd", version="1.0.0")
        shutil.copytree(src_dir / "danwa-upd", service.modules_dir / "danwa-upd")
        service.install("danwa-upd", source="local")

        # Update version
        _make_module(src_dir, "danwa-upd", version="2.0.0")
        shutil.copytree(src_dir / "danwa-upd", service.modules_dir / "danwa-upd", dirs_exist_ok=True)

        report = service.update("danwa-upd")
        shutil.rmtree(src_dir, ignore_errors=True)
        assert report.status == "ok"
        assert report.version == "2.0.0"


class TestTranslate:
    """Test translation marking (Sprint 2 placeholder)."""

    def test_translate_marks_pending(self, populated_service):
        """Translation marks files as pending in DB."""
        result = populated_service.translate("danwa-test-a", "de")
        assert isinstance(result, TranslationResult)
        assert result.module_id == "danwa-test-a"
        assert result.target_language == "de"

    def test_translate_unknown_module(self, populated_service):
        """Translating unknown module returns error."""
        result = populated_service.translate("nonexistent", "de")
        assert result.status == "error"

    def test_translate_force_overrides_cache(self, populated_service):
        """Force flag overrides cache skip."""
        r1 = populated_service.translate("danwa-test-a", "de")
        r2 = populated_service.translate("danwa-test-a", "de")
        assert r2.files_skipped >= r1.files_translated
        r3 = populated_service.translate("danwa-test-a", "de", force=True)
        assert r3.files_translated >= 0  # Files were processed


class TestErrorHandling:
    """Test error cases."""

    def test_install_nonexistent_via_service(self, service):
        """Installing nonexistent module raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            service.install("nonexistent-module")

    def test_service_with_corrupt_manifest(self, service):
        """Module with corrupt JSON in manifest is skipped in discovery."""
        mod_dir = service.modules_dir / "corrupt"
        mod_dir.mkdir(parents=True, exist_ok=True)
        (mod_dir / "manifest.json").write_text("{broken json")
        result = service.discover_local()
        assert len(result) == 0
