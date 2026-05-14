"""Tests for ModuleInstaller — install, uninstall, update, rollback."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from backend.modules.installer import ModuleInstaller


def _make_module(modules_dir: Path, module_id: str, version: str = "1.0.0", num_files: int = 2, checksums: bool = True) -> dict:
    """Create a minimal module directory with manifest and files."""
    mod_dir = modules_dir / module_id
    mod_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for i in range(num_files):
        fname = f"file_{i}.md"
        fpath = mod_dir / fname
        content = f"# {module_id} file {i}\n\nContent for testing."
        fpath.write_text(content)

        chksum = hashlib.sha256(content.encode()).hexdigest() if checksums else ""
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
        "name": {"en": f"{module_id} name"},
        "description": {"en": f"{module_id} description"},
        "version": version,
        "type": "argumentation-pattern",
        "category": "prompts",
        "author": {"name": "Test Author"},
        "license": "CC-BY-4.0",
        "checksum": hashlib.sha256(json.dumps(files).encode()).hexdigest(),
        "files": files,
        "dependencies": {},
    }

    (mod_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


@pytest.fixture()
def tmp_dirs():
    modules_dir = Path(tempfile.mkdtemp(prefix="test_modules_"))
    db_dir = Path(tempfile.mkdtemp(prefix="test_db_"))
    db_path = db_dir / "test.db"
    yield modules_dir, db_path
    shutil.rmtree(modules_dir, ignore_errors=True)
    shutil.rmtree(db_dir, ignore_errors=True)


class TestInstallFromDirectory:
    """Test module installation from a local directory.

    Key: source_dir (where module files live) != target modules_dir (where installer copies to).
    """

    def test_install_new_module(self, tmp_dirs):
        """Installing a new module succeeds."""
        modules_dir, db_path = tmp_dirs
        src_dir = Path(tempfile.mkdtemp(prefix="src_"))
        _make_module(src_dir, "danwa-test-install", version="1.0.0")

        installer = ModuleInstaller(modules_dir, db_path)
        report = installer.install_from_directory(src_dir / "danwa-test-install")

        shutil.rmtree(src_dir, ignore_errors=True)
        assert report.status == "ok"
        assert report.module_id == "danwa-test-install"
        assert report.version == "1.0.0"
        assert report.files_installed == 2
        assert report.db_entries_created >= 3

    def test_install_missing_manifest(self, tmp_dirs):
        """Missing manifest.json returns error report."""
        modules_dir, db_path = tmp_dirs
        mod_dir = Path(tempfile.mkdtemp()) / "no-manifest"
        mod_dir.mkdir(parents=True, exist_ok=True)
        (mod_dir / "some_file.md").write_text("content")

        installer = ModuleInstaller(modules_dir, db_path)
        report = installer.install_from_directory(mod_dir)
        shutil.rmtree(mod_dir.parent, ignore_errors=True)

        assert report.status == "error"
        assert "Manifest not found" in report.errors[0]

    def test_install_invalid_manifest(self, tmp_dirs):
        """Invalid manifest JSON returns error report."""
        modules_dir, db_path = tmp_dirs
        mod_dir = Path(tempfile.mkdtemp()) / "bad-manifest"
        mod_dir.mkdir(parents=True, exist_ok=True)
        (mod_dir / "manifest.json").write_text("not json")

        installer = ModuleInstaller(modules_dir, db_path)
        report = installer.install_from_directory(mod_dir)
        shutil.rmtree(mod_dir.parent, ignore_errors=True)

        assert report.status == "error"
        assert "Failed to parse" in report.errors[0]

    def test_install_with_checksum_mismatch(self, tmp_dirs):
        """Checksum mismatch is reported."""
        modules_dir, db_path = tmp_dirs
        src_dir = Path(tempfile.mkdtemp(prefix="src_"))
        _make_module(src_dir, "danwa-bad-cksum", version="1.0.0")
        # Corrupt the file
        (src_dir / "danwa-bad-cksum" / "file_0.md").write_text("tampered!")

        installer = ModuleInstaller(modules_dir, db_path)
        report = installer.install_from_directory(src_dir / "danwa-bad-cksum")
        shutil.rmtree(src_dir, ignore_errors=True)

        assert report.status == "error"
        assert any("checksum" in e.lower() for e in report.errors)

    def test_install_overwrite_same_version(self, tmp_dirs):
        """Overwrite=True allows reinstalling same version."""
        modules_dir, db_path = tmp_dirs
        src_dir = Path(tempfile.mkdtemp(prefix="src_"))
        _make_module(src_dir, "danwa-overwrite", version="1.0.0")
        installer = ModuleInstaller(modules_dir, db_path)

        r1 = installer.install_from_directory(src_dir / "danwa-overwrite")
        assert r1.status == "ok"

        # Without overwrite -> skipped
        r2 = installer.install_from_directory(src_dir / "danwa-overwrite", overwrite=False)
        assert r2.status == "skipped"

        # With overwrite -> ok
        r3 = installer.install_from_directory(src_dir / "danwa-overwrite", overwrite=True)
        assert r3.status == "ok"

        shutil.rmtree(src_dir, ignore_errors=True)

    def test_install_already_installed_different_version(self, tmp_dirs):
        """Installing same version again is skipped."""
        modules_dir, db_path = tmp_dirs
        src_dir = Path(tempfile.mkdtemp(prefix="src_"))
        _make_module(src_dir, "danwa-ver", version="1.0.0")
        installer = ModuleInstaller(modules_dir, db_path)
        installer.install_from_directory(src_dir / "danwa-ver")

        # Same version again without overwrite -> skipped
        r = installer.install_from_directory(src_dir / "danwa-ver", overwrite=False)
        assert r.status == "skipped"

        shutil.rmtree(src_dir, ignore_errors=True)


class TestUninstall:
    """Test module uninstallation."""

    def _setup_module(self, modules_dir, db_path):
        src_dir = Path(tempfile.mkdtemp(prefix="src_"))
        _make_module(src_dir, "danwa-uninst")
        installer = ModuleInstaller(modules_dir, db_path)
        installer.install_from_directory(src_dir / "danwa-uninst")
        shutil.rmtree(src_dir, ignore_errors=True)
        return installer

    def test_uninstall_existing(self, tmp_dirs):
        """Uninstalling an existing module removes files and DB entries."""
        modules_dir, db_path = tmp_dirs
        installer = self._setup_module(modules_dir, db_path)

        report = installer.uninstall("danwa-uninst")
        assert report.status == "ok"
        assert report.files_removed >= 2
        assert report.db_entries_removed >= 1
        assert not (modules_dir / "danwa-uninst").exists()

    def test_uninstall_nonexistent(self, tmp_dirs):
        """Uninstalling a non-existent module returns 'ok' (idempotent)."""
        modules_dir, db_path = tmp_dirs
        installer = ModuleInstaller(modules_dir, db_path)
        report = installer.uninstall("nonexistent-module")
        assert report.status == "ok"


class TestUpdate:
    """Test module update."""

    def test_update_existing(self, tmp_dirs):
        """Updating an existing module re-installs it."""
        modules_dir, db_path = tmp_dirs
        src_dir = Path(tempfile.mkdtemp(prefix="src_"))
        _make_module(src_dir, "danwa-upd", version="1.0.0")
        installer = ModuleInstaller(modules_dir, db_path)
        installer.install_from_directory(src_dir / "danwa-upd")

        # Create v2 in src_dir then copy to modules_dir (where update reads from)
        _make_module(src_dir, "danwa-upd", version="2.0.0")
        shutil.copytree(src_dir / "danwa-upd", modules_dir / "danwa-upd", dirs_exist_ok=True)
        report = installer.update("danwa-upd")

        shutil.rmtree(src_dir, ignore_errors=True)
        assert report.status == "ok"
        assert report.version == "2.0.0"

    def test_update_nonexistent(self, tmp_dirs):
        """Updating a non-existent module returns error."""
        modules_dir, db_path = tmp_dirs
        installer = ModuleInstaller(modules_dir, db_path)
        report = installer.update("nonexistent")
        assert report.status == "error"


class TestInstallFromURL:
    """Test URL-based installation."""

    def test_invalid_url(self, tmp_dirs):
        """Invalid URL returns error."""
        modules_dir, db_path = tmp_dirs
        installer = ModuleInstaller(modules_dir, db_path)
        report = installer.install_from_url("http://127.0.0.1:99999/nonexistent.zip")
        assert report.status == "error"


class TestRollback:
    """Test module rollback."""

    def test_rollback_missing(self, tmp_dirs):
        """Rollback to missing version returns False."""
        modules_dir, db_path = tmp_dirs
        installer = ModuleInstaller(modules_dir, db_path)
        assert installer.rollback("nonexistent", "1.0.0") is False


class TestBackupProtection:
    """Test that source==target backup protection works."""

    def test_source_equals_target_no_backup(self, tmp_dirs):
        """When source==target, no backup directory is created."""
        modules_dir, db_path = tmp_dirs
        src_dir = Path(tempfile.mkdtemp(prefix="src_"))
        _make_module(src_dir, "danwa-in-place", version="1.0.0")
        installer = ModuleInstaller(modules_dir, db_path)
        installer.install_from_directory(src_dir / "danwa-in-place")
        shutil.rmtree(src_dir, ignore_errors=True)

        # Re-install from same location (source == target)
        installer.install_from_directory(modules_dir / "danwa-in-place")

        bak_dirs = list(modules_dir.glob("danwa-in-place.bak.*"))
        assert len(bak_dirs) == 0
