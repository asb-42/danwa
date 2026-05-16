"""Module management API router.

Provides CRUD endpoints for installing, uninstalling, updating,
and discovering Danwa modules.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.modules.service import ModuleService

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level service instance (singleton)
_module_service: ModuleService | None = None


def get_module_service() -> ModuleService:
    """Get or create the module service singleton."""
    global _module_service
    if _module_service is None:
        _module_service = ModuleService()
    return _module_service


# ------------------------------------------------------------------
# Discovery & Listing
# ------------------------------------------------------------------


@router.get("/", response_model=list[dict[str, Any]])
async def list_modules(
    category: str | None = Query(None, description="Filter by category"),
) -> list[dict[str, Any]]:
    """List all installed modules with DB status."""
    svc = get_module_service()
    if category:
        modules = svc.list_all(category=category)
        return [
            {
                "module_id": m.module_id,
                "name": m.name,
                "description": m.description,
                "version": m.version,
                "type": m.type,
                "category": m.category,
                "author": m.author,
                "license": m.license,
                "tags": m.tags,
                "language": m.language,
                "checksum": m.checksum,
                "installed": m.installed,
                "enabled": m.enabled,
                "installed_at": str(m.installed_at) if m.installed_at else None,
                "updated_at": str(m.updated_at) if m.updated_at else None,
                "dependencies": m.dependencies,
                "file_count": m.file_count,
            }
            for m in modules
        ]
    return svc.discover_local_with_status()


@router.get("/available", response_model=list[dict[str, Any]])
async def list_available_modules() -> list[dict[str, Any]]:
    """List modules available for installation from the official registry.

    Currently returns a static list of known official modules.
    In the future, this will query a remote registry URL.
    """
    return [
        {
            "module_id": "danwa-prompts-base",
            "name": {"en": "Danwa Prompts Base (EN)", "de": "Danwa Prompts Basis (EN)"},
            "description": {"en": "Core English prompt templates and argumentation patterns"},
            "version": "0.5.0",
            "type": "argumentation-pattern",
            "category": "prompts",
            "author": {"name": "Danwa Community"},
            "license": "CC-BY-4.0",
            "tags": ["official", "prompts", "en"],
            "language": "en",
        },
        {
            "module_id": "danwa-agents-base",
            "name": {"en": "Danwa Agent Personas", "de": "Danwa Agent-Personas"},
            "description": {"en": "Default agent personas for debate roles"},
            "version": "0.5.0",
            "type": "agent-persona",
            "category": "agents",
            "author": {"name": "Danwa Community"},
            "license": "CC-BY-4.0",
            "tags": ["official", "agents", "en"],
            "language": "en",
        },
        {
            "module_id": "danwa-llm-profiles",
            "name": {"en": "Danwa LLM Profiles", "de": "Danwa LLM-Profile"},
            "description": {"en": "LLM configuration profiles for various providers"},
            "version": "0.5.0",
            "type": "llm-profile",
            "category": "llm-profiles",
            "author": {"name": "Danwa Community"},
            "license": "CC-BY-4.0",
            "tags": ["official", "llm"],
            "language": "en",
        },
        {
            "module_id": "danwa-workflow-templates",
            "name": {"en": "Danwa Workflow Templates", "de": "Danwa Workflow-Vorlagen"},
            "description": {"en": "Pre-built workflow templates for various debate formats"},
            "version": "0.5.0",
            "type": "workflow-template",
            "category": "workflows",
            "author": {"name": "Danwa Community"},
            "license": "CC-BY-4.0",
            "tags": ["official", "workflows"],
            "language": "en",
        },
        {
            "module_id": "danwa-workflow-variants",
            "name": {"en": "Danwa Workflow Variants", "de": "Danwa Workflow-Varianten"},
            "description": {"en": "Workflow execution variants (concise, formal, etc.)"},
            "version": "0.5.0",
            "type": "workflow-variant",
            "category": "workflow-variants",
            "author": {"name": "Danwa Community"},
            "license": "CC-BY-4.0",
            "tags": ["official", "workflows", "variants"],
            "language": "en",
        },
        {
            "module_id": "danwa-tone-profiles",
            "name": {"en": "Danwa Tone Profiles", "de": "Danwa Ton-Profile"},
            "description": {"en": "System tone profiles for debate style configuration (heated, academic, neutral)"},
            "version": "0.5.0",
            "type": "tone-profile",
            "category": "tone-profiles",
            "author": {"name": "Danwa Community"},
            "license": "CC-BY-4.0",
            "tags": ["official", "tone-profiles", "system"],
            "language": "en",
        },
        {
            "module_id": "danwa-role-types",
            "name": {"en": "Danwa Role Types", "de": "Danwa Rollentypen"},
            "description": {"en": "Core role types defining agent behavioral categories (strategist, critic, optimizer, moderator, etc.)"},
            "version": "0.5.0",
            "type": "role-type",
            "category": "role-types",
            "author": {"name": "Danwa Community"},
            "license": "CC-BY-4.0",
            "tags": ["official", "role-types", "system"],
            "language": "en",
        },
    ]


@router.get("/{module_id}", response_model=dict[str, Any])
async def get_module(module_id: str) -> dict[str, Any]:
    """Get detailed info about a specific module."""
    svc = get_module_service()
    info = svc.get(module_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Module '{module_id}' not found")
    return {
        "module_id": info.module_id,
        "name": info.name,
        "description": info.description,
        "version": info.version,
        "type": info.type,
        "category": info.category,
        "author": info.author,
        "license": info.license,
        "tags": info.tags,
        "language": info.language,
        "checksum": info.checksum,
        "installed": info.installed,
        "enabled": info.enabled,
        "installed_at": str(info.installed_at) if info.installed_at else None,
        "updated_at": str(info.updated_at) if info.updated_at else None,
        "dependencies": info.dependencies,
        "file_count": info.file_count,
    }


# ------------------------------------------------------------------
# Installation & Removal
# ------------------------------------------------------------------


class InstallRequest(BaseModel):
    """Request body for module installation."""

    module_id: str = Field(..., description="Module ID to install")
    source: str = Field("local", description="Source: 'local' or 'url'")
    source_url: str | None = Field(None, description="URL for remote installation")
    overwrite: bool = Field(False, description="Overwrite existing installation")


@router.post("/install", response_model=dict[str, Any], status_code=201)
async def install_module(body: InstallRequest) -> dict[str, Any]:
    """Install a module from local files or a URL."""
    svc = get_module_service()
    try:
        if body.source == "url" and body.source_url:
            report = svc.install(body.module_id, source="url", source_url=body.source_url)
        else:
            report = svc.install(body.module_id, source="local")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": report.status,
        "module_id": report.module_id,
        "version": report.version,
        "files_installed": report.files_installed,
        "files_failed": report.files_failed,
        "db_entries_created": report.db_entries_created,
        "checksum": report.checksum,
        "warnings": report.warnings,
        "errors": report.errors,
    }


class UninstallRequest(BaseModel):
    """Request body for module uninstallation."""

    force: bool = Field(False, description="Force uninstall ignoring dependencies")


@router.post("/{module_id}/uninstall", response_model=dict[str, Any])
async def uninstall_module(module_id: str, body: UninstallRequest) -> dict[str, Any]:
    """Uninstall a module."""
    svc = get_module_service()
    report = svc.uninstall(module_id, force=body.force)

    if report.status == "blocked":
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Cannot uninstall '{module_id}': other modules depend on it",
                "blocked_by": report.blocked_by,
            },
        )

    return {
        "status": report.status,
        "module_id": report.module_id,
        "files_removed": report.files_removed,
        "db_entries_removed": report.db_entries_removed,
        "warnings": report.warnings,
    }


@router.put("/{module_id}/update", response_model=dict[str, Any])
async def update_module(module_id: str) -> dict[str, Any]:
    """Update a module to the latest available version."""
    svc = get_module_service()
    try:
        report = svc.update(module_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if report.status == "error":
        raise HTTPException(status_code=404, detail=report.errors[0] if report.errors else "Update failed")

    return {
        "status": report.status,
        "module_id": report.module_id,
        "version": report.version,
        "files_installed": report.files_installed,
        "files_failed": report.files_failed,
        "warnings": report.warnings,
        "errors": report.errors,
    }


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


class ValidateRequest(BaseModel):
    """Request body for module validation."""

    manifest: dict[str, Any] = Field(..., description="Module manifest dict")


@router.post("/validate", response_model=dict[str, Any])
async def validate_module(body: ValidateRequest) -> dict[str, Any]:
    """Validate a module manifest without installing it."""
    svc = get_module_service()
    result = svc.validator.validate_manifest(body.manifest)
    return {
        "module_id": result.module_id,
        "valid": result.valid,
        "file_count": result.file_count,
        "checksum_valid": result.checksum_valid,
        "issues": [{"severity": i.severity, "field": i.field, "message": i.message} for i in result.issues],
    }


# ------------------------------------------------------------------
# Translation
# ------------------------------------------------------------------


class TranslateRequest(BaseModel):
    """Request body for module translation."""

    target_language: str = Field(..., description="Target language code (e.g. 'de')")
    force: bool = Field(False, description="Force re-translation")


@router.post("/{module_id}/translate", response_model=dict[str, Any])
async def translate_module(module_id: str, body: TranslateRequest) -> dict[str, Any]:
    """Initiate translation of a module to the target language."""
    svc = get_module_service()
    result = svc.translate(module_id, body.target_language, force=body.force)
    return {
        "module_id": result.module_id,
        "target_language": result.target_language,
        "files_translated": result.files_translated,
        "files_skipped": result.files_skipped,
        "quality_scores": result.quality_scores,
        "status": result.status,
        "estimated_cost_usd": result.estimated_cost_usd,
    }


@router.get("/{module_id}/translations", response_model=dict[str, Any])
async def get_translation_status(module_id: str) -> dict[str, Any]:
    """Get the translation status for all files in a module."""
    svc = get_module_service()
    try:
        import sqlite3

        conn = sqlite3.connect(str(svc.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT file_path, language, source_hash, quality_score, approved, generated_at FROM module_translation_cache WHERE module_id = ?",
            (module_id,),
        )
        entries = []
        for row in cursor.fetchall():
            entries.append(
                {
                    "file_path": row["file_path"],
                    "language": row["language"],
                    "source_hash": row["source_hash"],
                    "quality_score": row["quality_score"],
                    "approved": bool(row["approved"]) if "approved" in row.keys() else False,
                    "generated_at": row["generated_at"],
                }
            )
        conn.close()
        return {"module_id": module_id, "translations": entries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Enable / Disable (Activation)
# ------------------------------------------------------------------


@router.post("/{module_id}/enable", response_model=dict[str, Any])
async def enable_module(module_id: str) -> dict[str, Any]:
    """Enable (activate) a module."""
    svc = get_module_service()
    try:
        import sqlite3

        conn = sqlite3.connect(str(svc.db_path))
        cursor = conn.cursor()
        cursor.execute("UPDATE module_registry SET enabled = 1 WHERE id = ?", (module_id,))
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Module '{module_id}' not found in registry")
        conn.commit()
        conn.close()
        logger.info("Enabled module %s", module_id)
        return {"status": "ok", "module_id": module_id, "enabled": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{module_id}/disable", response_model=dict[str, Any])
async def disable_module(module_id: str) -> dict[str, Any]:
    """Disable (deactivate) a module."""
    svc = get_module_service()
    try:
        import sqlite3

        conn = sqlite3.connect(str(svc.db_path))
        cursor = conn.cursor()
        cursor.execute("UPDATE module_registry SET enabled = 0 WHERE id = ?", (module_id,))
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Module '{module_id}' not found in registry")
        conn.commit()
        conn.close()
        logger.info("Disabled module %s", module_id)
        return {"status": "ok", "module_id": module_id, "enabled": False}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Export (ZIP for sharing)
# ------------------------------------------------------------------


@router.post("/{module_id}/export")
async def export_module(module_id: str) -> Any:
    """Export a module as a ZIP archive for sharing/uploading to GitHub."""
    from fastapi.responses import StreamingResponse
    import io
    import zipfile

    svc = get_module_service()
    module_dir = svc.modules_dir / module_id
    if not module_dir.exists():
        raise HTTPException(status_code=404, detail=f"Module directory not found: {module_dir}")

    manifest_path = module_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail=f"Manifest not found for module '{module_id}'")

    # Load manifest to get file list
    import json
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add manifest
        zf.write(str(manifest_path), f"{module_id}/manifest.json")

        # Add all module files
        for file_entry in manifest_data.get("files", []):
            fpath = module_dir / file_entry["path"]
            if fpath.exists():
                zf.write(str(fpath), f"{module_id}/{file_entry['path']}")

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={module_id}.zip"},
    )
