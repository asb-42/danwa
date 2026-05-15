"""Integration tests for the backup API endpoints."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


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
    return dd


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    cd = tmp_path / "config"
    cd.mkdir()
    (cd / "settings.yaml").write_text("ui:\n  language: en\n")
    return cd


@pytest.fixture()
def app_with_backup(app, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
    app.state.backup_dir = backup_dir
    return app


class TestCreateBackupAPI:
    def test_create_backup_returns_200(self, client, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            response = client.post("/api/v1/config/backup", json={"trigger": "manual"})
            assert response.status_code == 200
            data = response.json()
            assert "backup_id" in data
            assert data["backup_id"].endswith(".zip")
            assert data["file_count"] > 0
        finally:
            os.chdir(original_cwd)

    def test_create_backup_shutdown_trigger(self, client, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            response = client.post("/api/v1/config/backup", json={"trigger": "shutdown"})
            assert response.status_code == 200
            data = response.json()
            assert "backup_id" in data
        finally:
            os.chdir(original_cwd)


class TestListBackupsAPI:
    def test_list_backups_empty(self, client):
        response = client.get("/api/v1/config/backups")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["backups"] == []

    def test_list_backups_after_create(self, client, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            client.post("/api/v1/config/backup", json={"trigger": "manual"})
            response = client.get("/api/v1/config/backups")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["backups"]) == 1
            assert data["backups"][0]["trigger"] == "manual"
        finally:
            os.chdir(original_cwd)


class TestGetBackupAPI:
    def test_get_backup_metadata(self, client, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            create_resp = client.post("/api/v1/config/backup", json={"trigger": "manual"})
            backup_id = create_resp.json()["backup_id"]

            response = client.get(f"/api/v1/config/backups/{backup_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["backup_id"] == backup_id
            assert "app_version" in data
        finally:
            os.chdir(original_cwd)

    def test_get_nonexistent_backup_returns_404(self, client):
        response = client.get("/api/v1/config/backups/nonexistent.zip")
        assert response.status_code == 404


class TestListBackupFilesAPI:
    def test_list_files_in_backup(self, client, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            create_resp = client.post("/api/v1/config/backup", json={"trigger": "manual"})
            backup_id = create_resp.json()["backup_id"]

            response = client.get(f"/api/v1/config/backups/{backup_id}/files")
            assert response.status_code == 200
            data = response.json()
            assert data["backup_id"] == backup_id
            assert len(data["files"]) > 0
        finally:
            os.chdir(original_cwd)


class TestVerifyBackupAPI:
    def test_verify_valid_backup(self, client, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            create_resp = client.post("/api/v1/config/backup", json={"trigger": "manual"})
            backup_id = create_resp.json()["backup_id"]

            response = client.post(f"/api/v1/config/backups/{backup_id}/verify", json={"backup_id": backup_id})
            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is True
            assert data["errors"] == []
        finally:
            os.chdir(original_cwd)


class TestRestoreBackupAPI:
    def test_restore_backup(self, client, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            create_resp = client.post("/api/v1/config/backup", json={"trigger": "manual"})
            backup_id = create_resp.json()["backup_id"]

            import shutil

            shutil.rmtree(tmp_path / "data")
            shutil.rmtree(tmp_path / "config")

            response = client.post(f"/api/v1/config/backups/{backup_id}/restore", json={"backup_id": backup_id})
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["restored_files"] > 0
        finally:
            os.chdir(original_cwd)


class TestDeleteBackupAPI:
    def test_delete_backup(self, client, tmp_path: Path, data_dir: Path, config_dir: Path, backup_dir: Path):
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            create_resp = client.post("/api/v1/config/backup", json={"trigger": "manual"})
            backup_id = create_resp.json()["backup_id"]

            response = client.delete(f"/api/v1/config/backups/{backup_id}")
            assert response.status_code == 200

            response = client.get(f"/api/v1/config/backups/{backup_id}")
            assert response.status_code == 404
        finally:
            os.chdir(original_cwd)


class TestBackupSettingsAPI:
    def test_get_backup_settings(self, client):
        response = client.get("/api/v1/config/backup-settings")
        assert response.status_code == 200
        data = response.json()
        assert "backup_enabled" in data
        assert "backup_auto_on_shutdown" in data
        assert "backup_retention_count" in data

    def test_update_backup_settings(self, client):
        response = client.put(
            "/api/v1/config/backup-settings",
            json={
                "backup_enabled": True,
                "backup_auto_on_shutdown": True,
                "backup_retention_count": 5,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
