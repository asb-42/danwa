"""API router for application settings and language configuration.

Profile management (LLM profiles, agent personas, prompt variants) has
been moved to the ``profiles`` router.
"""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_project_store
from backend.core.config import is_service_llm_eligible
from backend.core.config import settings as app_settings
from backend.persistence.backup import BackupResult, BackupService, VerificationResult
from backend.services.dms.config import DEFAULT_DMS_CONFIG
from backend.services.profile_service import ProfileService

logger = logging.getLogger(__name__)

router = APIRouter()

_SETTINGS_PATH = Path("config/settings.yaml")

SUPPORTED_LANGUAGES = {
    "de": "Deutsch",
    "en": "English",
    "fr": "Français",
    "es": "Español",
    "it": "Italiano",
    "pt": "Português",
    "ru": "Русский",
    "zh": "中文",
    "ja": "日本語",
    "ko": "한국어",
    "sv": "Svenska",
    "el": "Ελληνικά",
    "ar": "العربية",
    "he": "עברית",
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


def _load_project_config(project_id: str) -> dict[str, Any]:
    """Load project-specific config, falling back to global settings."""
    project = get_project_store().get(project_id)
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
def get_project_settings(project_id: str) -> dict:
    """Get settings for a specific project (merged with global defaults)."""
    return _load_project_config(project_id)


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
async def get_version():
    """Return the current application version from the single source of truth."""
    commit = ""
    try:
        commit = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit = os.environ.get("GIT_COMMIT_HASH", "")

    return {
        "version": app_settings.app_version,
        "build": datetime.now(UTC).isoformat(),
        "commit": commit,
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
def verify_backup(backup_id: str):
    """Verify the integrity of a backup.

    Checks the ZIP structure and validates SHA-256 checksums.
    """
    if not app_settings.backup_enabled:
        raise HTTPException(status_code=403, detail="Backup is disabled in settings")

    service = _get_backup_service()
    result: VerificationResult = service.verify_backup(backup_id)
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
    settings = _load_settings()
    if "backup" not in settings:
        settings["backup"] = {}
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        settings["backup"][key] = value
    _save_settings(settings)
    for key, value in update_data.items():
        if hasattr(app_settings, key):
            setattr(app_settings, key, value)
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


# --- OCR Settings ---


@router.get("/ocr-settings")
def get_ocr_settings():
    """Get current OCR configuration from settings.yaml (merged with defaults)."""
    settings = _load_settings()
    dms_config = {**DEFAULT_DMS_CONFIG, **(settings.get("dms") or {})}
    return {key: dms_config[key] for key in ("ocr_enabled", "ocr_device", "ocr_lang", "ocr_preferred_engine")}


class OcrSettingsBody(BaseModel):
    """Request body for OCR settings update.

    Only `ocr_preferred_engine` is user-configurable via the UI.
    """

    ocr_preferred_engine: str | None = None


@router.put("/ocr-settings")
def update_ocr_settings(body: OcrSettingsBody):
    """Update OCR settings in settings.yaml."""
    valid_engines = {"auto", "paddleocr", "easyocr", "tesseract"}
    if body.ocr_preferred_engine not in valid_engines:
        raise HTTPException(
            status_code=400,
            detail=f"ocr_preferred_engine must be one of: {', '.join(sorted(valid_engines))}",
        )
    settings = _load_settings()
    if "dms" not in settings:
        settings["dms"] = {}
    settings["dms"]["ocr_preferred_engine"] = body.ocr_preferred_engine
    _save_settings(settings)
    logger.info("OCR preferred engine set to: %s", body.ocr_preferred_engine)
    return {"status": "ok", "ocr_preferred_engine": body.ocr_preferred_engine}


# --- Utility LLM (Sprint 16) ---


class UtilityLLMRequest(BaseModel):
    """UtilityLLMRequest class."""

    profile_id: str


@router.get("/service-llm")
async def get_utility_llm_config():
    """Get the current utility LLM configuration."""
    return {
        "service_llm_profile_id": app_settings.service_llm_profile_id,
        "service_llm_min_context": app_settings.service_llm_min_context,
        "service_llm_blacklist": app_settings.service_llm_blacklist,
    }


@router.post("/validate-service-llm")
async def validate_utility_llm(body: UtilityLLMRequest):
    """Validate whether a given profile is suitable as utility LLM."""
    ps = ProfileService()
    profile = ps.get_llm_profile(body.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"LLM profile '{body.profile_id}' not found")
    eligible, reason = is_service_llm_eligible(profile)
    return {
        "profile_id": body.profile_id,
        "service_eligible": eligible,
        "reason": reason,
    }


@router.post("/service-llm")
async def set_utility_llm(body: UtilityLLMRequest):
    """Set or clear the utility LLM profile."""
    if not body.profile_id:
        app_settings.service_llm_profile_id = None
        settings = _load_settings()
        if "utility_llm" not in settings:
            settings["utility_llm"] = {}
        settings["utility_llm"]["service_llm_profile_id"] = None
        _save_settings(settings)
        logger.info("Utility LLM cleared")
        return {"status": "ok", "service_llm_profile_id": None}
    ps = ProfileService()
    profile = ps.get_llm_profile(body.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"LLM profile '{body.profile_id}' not found")
    eligible, reason = is_service_llm_eligible(profile)
    if not eligible:
        raise HTTPException(status_code=400, detail=f"Profile '{body.profile_id}' not eligible: {reason}")
    app_settings.service_llm_profile_id = body.profile_id
    settings = _load_settings()
    if "utility_llm" not in settings:
        settings["utility_llm"] = {}
    settings["utility_llm"]["service_llm_profile_id"] = body.profile_id
    _save_settings(settings)
    logger.info("Utility LLM changed to %s", body.profile_id)
    return {"status": "ok", "service_llm_profile_id": body.profile_id}
