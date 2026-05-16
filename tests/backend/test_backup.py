"""Unit tests for the BackupService."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.persistence.backup import (
    BackupMetadata,
    BackupResult,
    BackupService,
    RestoreResult,
    VerificationResult,
)


@pytest.fixture()
def backup_dir(tmp_path: Path) -> Path:
    bd = tmp_path / "backups"
    bd.mkdir()
    return bd


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    dd = tmp_path / "data"
    dd.mkdir()
    (dd / "audit.db").write_text("fake-db-content")
    proj = dd / "projects" / "test-proj"
    proj.mkdir(parents=True)
    (proj / "project.json").write_text('{"id": "test-proj", "name": "Test"}')
    debates = proj / "debates"
    debates.mkdir()
    (debates / "debate-1.json").write_text('{"debate_id": "d1"}')
    (debates / "debate-2.json").write_text('{"debate_id": "d2"}')
    dms = proj / "dms"
    dms.mkdir()
    (dms / "dms.db").write_text("fake-dms-db")
    return dd


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    cd = tmp_path / "config"
    cd.mkdir()
    (cd / "settings.yaml").write_text("ui:\n  language: en\n")
    return cd


@pytest.fixture()
def service(tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path) -> BackupService:
    settings = Settings(
        app_version="2.0.0",
        backup_dir=str(backup_dir),
    )
    service = BackupService(
        project_root=tmp_path,
        include_paths=[
            "data/projects",
            "data/audit.db",
            "config/settings.yaml",
        ],
        settings=settings,
    )
    service.BACKUP_DIR = backup_dir
    return service


class TestBackupResult:
    def test_to_dict(self):
        from datetime import UTC, datetime

        result = BackupResult(
            backup_id="test.zip",
            path="backups/test.zip",
            size_bytes=1024,
            file_count=5,
            created_at=datetime.now(UTC),
            sha256="abc123",
            duration_seconds=1.5,
        )
        d = result.to_dict()
        assert d["backup_id"] == "test.zip"
        assert d["size_bytes"] == 1024
        assert d["file_count"] == 5
        assert d["sha256"] == "abc123"
        assert isinstance(d["duration_seconds"], float)


class TestBackupMetadata:
    def test_to_dict(self):
        from datetime import UTC, datetime

        meta = BackupMetadata(
            backup_id="test.zip",
            created_at=datetime.now(UTC),
            app_version="2.0.0",
            commit_hash="abc123",
            file_count=10,
            size_bytes=2048,
            trigger="manual",
            sha256="def456",
        )
        d = meta.to_dict()
        assert d["backup_id"] == "test.zip"
        assert d["app_version"] == "2.0.0"
        assert d["trigger"] == "manual"


class TestVerificationResult:
    def test_to_dict_valid(self):
        result = VerificationResult(valid=True, errors=[], file_count_verified=5)
        d = result.to_dict()
        assert d["valid"] is True
        assert d["errors"] == []
        assert d["file_count_verified"] == 5

    def test_to_dict_invalid(self):
        result = VerificationResult(
            valid=False,
            errors=["Hash mismatch: data/audit.db"],
            file_count_verified=3,
        )
        d = result.to_dict()
        assert d["valid"] is False
        assert len(d["errors"]) == 1


class TestRestoreResult:
    def test_defaults(self):
        result = RestoreResult(success=True, message="OK")
        assert result.success is True
        assert result.message == "OK"
        assert result.restored_files == 0

    def test_with_files(self):
        result = RestoreResult(success=True, message="OK", restored_files=42)
        assert result.restored_files == 42


class TestCreateBackup:
    def test_creates_zip_file(self, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            settings = Settings(app_version="2.0.0", backup_dir=str(backup_dir))
            service = BackupService(
                project_root=tmp_path,
                include_paths=["data/projects", "data/audit.db", "config/settings.yaml"],
                settings=settings,
            )
            service.BACKUP_DIR = backup_dir

            result = service.create_backup(trigger="manual")

            assert result.backup_id.endswith(".zip")
            assert result.file_count > 0
            assert result.size_bytes > 0
            assert len(result.sha256) == 64
            assert backup_dir / result.backup_id
        finally:
            os.chdir(original_cwd)

    def test_zip_contains_metadata_json(self, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        import os
        import zipfile

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            settings = Settings(app_version="2.0.0", backup_dir=str(backup_dir))
            service = BackupService(
                project_root=tmp_path,
                include_paths=["data/projects", "data/audit.db", "config/settings.yaml"],
                settings=settings,
            )
            service.BACKUP_DIR = backup_dir

            result = service.create_backup(trigger="manual")

            with zipfile.ZipFile(backup_dir / result.backup_id, "r") as zf:
                names = zf.namelist()
                assert "metadata.json" in names
                meta = json.loads(zf.read("metadata.json").decode("utf-8"))
                assert meta["version"] == 1
                assert meta["app_version"] == "2.0.0"
                assert meta["trigger"] == "manual"
        finally:
            os.chdir(original_cwd)

    def test_zip_contains_sha256sums(self, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        import os
        import zipfile

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            settings = Settings(app_version="2.0.0", backup_dir=str(backup_dir))
            service = BackupService(
                project_root=tmp_path,
                include_paths=["data/projects", "data/audit.db", "config/settings.yaml"],
                settings=settings,
            )
            service.BACKUP_DIR = backup_dir

            result = service.create_backup(trigger="manual")

            with zipfile.ZipFile(backup_dir / result.backup_id, "r") as zf:
                names = zf.namelist()
                assert "SHA-256SUMS" in names
                sums = zf.read("SHA-256SUMS").decode("utf-8")
                assert "data/audit.db" in sums
        finally:
            os.chdir(original_cwd)

    def test_zip_contains_project_data(self, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        import os
        import zipfile

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            settings = Settings(app_version="2.0.0", backup_dir=str(backup_dir))
            service = BackupService(
                project_root=tmp_path,
                include_paths=["data/projects", "data/audit.db", "config/settings.yaml"],
                settings=settings,
            )
            service.BACKUP_DIR = backup_dir

            result = service.create_backup(trigger="manual")

            with zipfile.ZipFile(backup_dir / result.backup_id, "r") as zf:
                names = zf.namelist()
                assert any("project.json" in n for n in names)
                assert any("debate" in n and n.endswith(".json") for n in names)
                assert any("audit.db" in n for n in names)
        finally:
            os.chdir(original_cwd)

    def test_excluded_patterns_not_included(self, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        import os
        import zipfile

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            (tmp_path / "logs").mkdir()
            (tmp_path / "logs" / "trace.jsonl").write_text("log data")
            (tmp_path / ".env").write_text("SECRET=123")

            settings = Settings(app_version="2.0.0", backup_dir=str(backup_dir))
            service = BackupService(
                project_root=tmp_path,
                include_paths=["data/projects", "data/audit.db", "config/settings.yaml", "logs", ".env"],
                settings=settings,
            )
            service.BACKUP_DIR = backup_dir

            result = service.create_backup(trigger="manual")

            with zipfile.ZipFile(backup_dir / result.backup_id, "r") as zf:
                names = zf.namelist()
                assert not any("logs/" in n for n in names)
                assert not any(".env" in n for n in names)
        finally:
            os.chdir(original_cwd)

    def test_shutdown_trigger(self, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        import os
        import zipfile

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            settings = Settings(app_version="2.0.0", backup_dir=str(backup_dir))
            service = BackupService(
                project_root=tmp_path,
                include_paths=["data/projects", "data/audit.db", "config/settings.yaml"],
                settings=settings,
            )
            service.BACKUP_DIR = backup_dir

            result = service.create_backup(trigger="shutdown")

            with zipfile.ZipFile(backup_dir / result.backup_id, "r") as zf:
                meta = json.loads(zf.read("metadata.json").decode("utf-8"))
                assert meta["trigger"] == "shutdown"
        finally:
            os.chdir(original_cwd)

    def test_nonexistent_paths_skipped(self, tmp_path: Path, backup_dir: Path):
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            settings = Settings(app_version="2.0.0", backup_dir=str(backup_dir))
            service = BackupService(
                project_root=tmp_path,
                include_paths=["nonexistent/path", "also/missing"],
                settings=settings,
            )
            service.BACKUP_DIR = backup_dir

            result = service.create_backup(trigger="manual")

            assert result.file_count == 0
        finally:
            os.chdir(original_cwd)


class TestListBackups:
    def test_empty_directory(self, tmp_path: Path, backup_dir: Path):
        service = BackupService(project_root=tmp_path, settings=Settings(app_version="2.0.0"))
        service.BACKUP_DIR = backup_dir
        assert service.list_backups() == []

    def test_lists_backups_sorted(self, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            settings = Settings(app_version="2.0.0", backup_dir=str(backup_dir))
            service = BackupService(
                project_root=tmp_path,
                include_paths=["data/projects", "data/audit.db", "config/settings.yaml"],
                settings=settings,
            )
            service.BACKUP_DIR = backup_dir

            service.create_backup(trigger="manual")
            import time

            time.sleep(1.1)
            service.create_backup(trigger="shutdown")

            backups = service.list_backups()
            assert len(backups) >= 2
            assert backups[0].trigger == "shutdown"
        finally:
            os.chdir(original_cwd)


class TestVerifyBackup:
    def test_valid_backup(self, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            settings = Settings(app_version="2.0.0", backup_dir=str(backup_dir))
            service = BackupService(
                project_root=tmp_path,
                include_paths=["data/projects", "data/audit.db", "config/settings.yaml"],
                settings=settings,
            )
            service.BACKUP_DIR = backup_dir

            result = service.create_backup(trigger="manual")
            verification = service.verify_backup(result.backup_id)

            assert verification.valid is True
            assert verification.errors == []
            assert verification.file_count_verified > 0
        finally:
            os.chdir(original_cwd)

    def test_nonexistent_backup(self, tmp_path: Path, backup_dir: Path):
        service = BackupService(project_root=tmp_path, settings=Settings(app_version="2.0.0"))
        service.BACKUP_DIR = backup_dir
        result = service.verify_backup("nonexistent.zip")
        assert result.valid is False
        assert len(result.errors) == 1
        assert "nicht gefunden" in result.errors[0]

    def test_invalid_zip_file(self, tmp_path: Path, backup_dir: Path):
        (backup_dir / "bad.zip").write_text("not a zip file")
        service = BackupService(project_root=tmp_path, settings=Settings(app_version="2.0.0"))
        service.BACKUP_DIR = backup_dir
        result = service.verify_backup("bad.zip")
        assert result.valid is False


class TestRestore:
    def test_restore_from_backup(self, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        import os
        import shutil

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            settings = Settings(app_version="2.0.0", backup_dir=str(backup_dir))
            service = BackupService(
                project_root=tmp_path,
                include_paths=["data/projects", "data/audit.db", "config/settings.yaml"],
                settings=settings,
            )
            service.BACKUP_DIR = backup_dir

            result = service.create_backup(trigger="manual")

            shutil.rmtree(tmp_path / "data")
            shutil.rmtree(tmp_path / "config")

            restore_result = BackupService.restore(backup_dir / result.backup_id)

            assert restore_result.success is True
            assert restore_result.restored_files > 0
        finally:
            os.chdir(original_cwd)

    def test_restore_nonexistent_file(self, tmp_path: Path):
        result = BackupService.restore(tmp_path / "nonexistent.zip")
        assert result.success is False
        assert "nicht gefunden" in result.message

    def test_restore_invalid_zip(self, tmp_path: Path):
        bad_file = tmp_path / "bad.zip"
        bad_file.write_text("not a zip")
        result = BackupService.restore(bad_file)
        assert result.success is False


class TestGetBackupFileList:
    def test_returns_file_list(self, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            settings = Settings(app_version="2.0.0", backup_dir=str(backup_dir))
            service = BackupService(
                project_root=tmp_path,
                include_paths=["data/projects", "data/audit.db", "config/settings.yaml"],
                settings=settings,
            )
            service.BACKUP_DIR = backup_dir

            result = service.create_backup(trigger="manual")
            files = service.get_backup_file_list(result.backup_id)

            assert len(files) > 0
            assert any("project.json" in f for f in files)
            assert any("audit.db" in f for f in files)
        finally:
            os.chdir(original_cwd)

    def test_nonexistent_backup_raises(self, tmp_path: Path, backup_dir: Path):
        service = BackupService(project_root=tmp_path, settings=Settings(app_version="2.0.0"))
        service.BACKUP_DIR = backup_dir
        with pytest.raises(FileNotFoundError):
            service.get_backup_file_list("nonexistent.zip")
