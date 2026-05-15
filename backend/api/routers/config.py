"""API router for application settings and language configuration.

Profile management (LLM profiles, agent personas, prompt variants) has
been moved to the ``profiles`` router.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_project_store
from backend.core.config import Settings
from backend.core.config import settings as app_settings
from backend.persistence.backup import BackupResult, BackupService, VerificationResult
from backend.persistence.project_store import ProjectStore

logger = logging.getLogger(__name__)

router = APIRouter()

_SETTINGS_PATH = Path("config/settings.yaml")

SUPPORTED_LANGUAGES = {
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
}


# --- Helpers ---


def _load_settings() -> dict[str, Any]:
    """Load settings from YAML file."""
    if not _SETTINGS_PATH.exists():
        return {}
    with open(_SETTINGS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_settings(data: dict[str, Any]) -> None:
    """Save settings to YAML file."""
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    logger.info("Settings saved to %s", _SETTINGS_PATH)


def _load_project_config(project_id: str, project_store) -> dict[str, Any]:
    """Load project-specific config, falling back to global settings."""
    project = project_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Start with global settings
    global_settings = _load_settings()

    # Overlay project-specific config
    project_config = project.config.model_dump(mode="json")
    # Merge: project config overrides global
    merged = {**global_settings}
    for key, value in project_config.items():
        if value is not None:
            merged[key] = value

    return merged


# --- Request bodies ---


class SettingsBody(BaseModel):
    """Generic settings update body."""

    settings: dict[str, Any]


class LanguageBody(BaseModel):
    """Language update body."""

    language: str


class BackupCreateBody(BaseModel):
    """Request body to create a backup."""

    trigger: str = "manual"


class BackupVerifyBody(BaseModel):
    """Request body to verify a backup."""

    backup_id: str


class BackupRestoreBody(BaseModel):
    """Request body to restore a backup.

    .. warning::
        This operation is destructive and overwrites existing data.
        The function is a placeholder and not yet implemented.
    """

    backup_id: str


# --- Settings ---


@router.get("/settings")
def get_settings() -> dict:
    """Get all application settings."""
    return _load_settings()


@router.put("/settings")
def update_settings(body: dict[str, Any]) -> dict:
    """Update application settings."""
    _save_settings(body)
    return {"status": "ok"}


@router.get("/settings/project/{project_id}")
def get_project_settings(project_id: str, project_store: ProjectStore = Depends(get_project_store)) -> dict:
    """Get settings for a specific project (merged with global defaults)."""
    return _load_project_config(project_id, project_store)


# --- Language ---


@router.get("/language")
def get_language() -> dict:
    """Get the current UI language."""
    settings = _load_settings()
    language = settings.get("ui", {}).get("language", "en")
    return {"language": language, "supported": SUPPORTED_LANGUAGES}


@router.put("/language")
def set_language(body: LanguageBody) -> dict:
    """Set the UI language."""
    if body.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {body.language}")
    settings = _load_settings()
    if "ui" not in settings:
        settings["ui"] = {}
    settings["ui"]["language"] = body.language
    _save_settings(settings)
    return {"status": "ok", "language": body.language}


# --- Version ---


@router.get("/version")
async def get_version(settings: Settings = Depends(get_settings)):
    """Return the current application version from the single source of truth."""
    return {
        "version": settings.app_version,
        "build": datetime.now(UTC).isoformat(),
    }


# --- Backup (Sprint 18) ---


def _get_backup_service() -> BackupService:
    """Create a BackupService with the current app settings."""
    return BackupService(settings=app_settings)


@router.post("/backup", response_model=dict)
def create_backup(body: BackupCreateBody = BackupCreateBody()):
    """Create a new backup archive.

    Creates a ZIP file containing all critical user data
    (projects, audit DB, configs, etc.).
    """
    if not app_settings.backup_enabled:
        raise HTTPException(status_code=403, detail="Backup is disabled in settings")

    service = _get_backup_service()
    result: BackupResult = service.create_backup(trigger=body.trigger)

    # Apply retention policy
    _apply_retention(service)

    return result.to_dict()


@router.get("/backups", response_model=dict)
def list_backups():
    """List all available backups with metadata."""
    if not app_settings.backup_enabled:
        raise HTTPException(status_code=403, detail="Backup is disabled in settings")

    service = _get_backup_service()
    backups = service.list_backups()
    return {
        "backups": [b.to_dict() for b in backups],
        "total": len(backups),
    }


@router.delete("/backups/{backup_id}", response_model=dict)
def delete_backup(backup_id: str):
    """Delete a backup archive."""
    if not app_settings.backup_enabled:
        raise HTTPException(status_code=403, detail="Backup is disabled in settings")

    service = _get_backup_service()
    backup_path = service.BACKUP_DIR / backup_id
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail=f"Backup not found: {backup_id}")
    backup_path.unlink()
    return {"status": "ok", "message": f"Backup deleted: {backup_id}"}


@router.get("/backups/{backup_id}", response_model=dict)
def get_backup(backup_id: str):
    """Get metadata for a specific backup."""
    if not app_settings.backup_enabled:
        raise HTTPException(status_code=403, detail="Backup is disabled in settings")

    service = _get_backup_service()
    backups = service.list_backups()
    for b in backups:
        if b.backup_id == backup_id:
            return b.to_dict()
    raise HTTPException(status_code=404, detail=f"Backup not found: {backup_id}")


@router.get("/backups/{backup_id}/files", response_model=dict)
def list_backup_files(backup_id: str):
    """List all files contained in a backup."""
    if not app_settings.backup_enabled:
        raise HTTPException(status_code=403, detail="Backup is disabled in settings")

    service = _get_backup_service()
    try:
        files = service.get_backup_file_list(backup_id)
        return {
            "backup_id": backup_id,
            "files": files,
            "file_count": len(files),
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Backup not found: {backup_id}")


@router.post("/backups/{backup_id}/verify", response_model=dict)
def verify_backup(body: BackupVerifyBody):
    """Verify the integrity of a backup.

    Checks the ZIP structure and validates SHA-256 checksums.
    """
    if not app_settings.backup_enabled:
        raise HTTPException(status_code=403, detail="Backup is disabled in settings")

    service = _get_backup_service()
    result: VerificationResult = service.verify_backup(body.backup_id)
    return result.to_dict()


@router.post("/backups/{backup_id}/restore", response_model=dict)
def restore_backup(body: BackupRestoreBody):
    """Restore data from a backup.

    .. warning::
        This is a DESTRUCTIVE operation — it will overwrite existing data.
    """
    service = _get_backup_service()
    backup_path = service.BACKUP_DIR / body.backup_id
    result = BackupService.restore(backup_path)
    return {
        "success": result.success,
        "message": result.message,
        "restored_files": result.restored_files,
    }


class BackupSettingsBody(BaseModel):
    """Request body for backup settings update."""

    backup_enabled: bool | None = None
    backup_auto_on_shutdown: bool | None = None
    backup_retention_count: int | None = None
    backup_encrypt: bool | None = None
    backup_dir: str | None = None



@router.get("/backup-settings", response_model=dict)
def get_backup_settings():
    """Get current backup settings."""
    return {
        "backup_enabled": app_settings.backup_enabled,
        "backup_auto_on_shutdown": app_settings.backup_auto_on_shutdown,
        "backup_retention_count": app_settings.backup_retention_count,
        "backup_encrypt": app_settings.backup_encrypt,
        "backup_dir": str(app_settings.backup_dir),
    }


@router.put("/backup-settings", response_model=dict)
def update_backup_settings(body: BackupSettingsBody):
    """Update backup settings."""
    from backend.core.config import Settings

    current = Settings()
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current, key, value)
    current.save()
    return {"status": "ok", "settings": get_backup_settings()}


def _apply_retention(service: BackupService) -> None:
    """Remove old backups based on the retention setting.

    Deletes the oldest backups when the count exceeds
    `backup_retention_count`. A value of 0 means unlimited retention.
    """
    retention = app_settings.backup_retention_count
    if retention <= 0:
        return  # Unlimited retention

    backups = service.list_backups()
    # Oldest first — delete from the beginning
    to_delete = sorted(backups, key=lambda b: b.created_at)[:-retention]

    for b in to_delete:
        try:
            backup_path = service.BACKUP_DIR / b.backup_id
            if backup_path.exists():
                backup_path.unlink()
                logger.info("Old backup removed: %s", b.backup_id)
        except OSError as exc:
            logger.warning("Could not delete backup %s: %s", b.backup_id, exc)
