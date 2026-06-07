"""Module management API router.

Provides CRUD endpoints for installing, uninstalling, updating,
and discovering Danwa modules.
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
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
                "created_at": str(m.created_at) if m.created_at else None,
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

    Currently returns an empty list — all modules are discovered from the
    local `modules/` directory. A remote registry may be added later.
    """
    return []


# ------------------------------------------------------------------
# Repository Integration (danwa-modules)
# ------------------------------------------------------------------


@router.get("/repo-index", response_model=list[dict[str, Any]])
def get_repo_index(
    force_refresh: bool = Query(False, description="Bypass cache and fetch fresh index"),
) -> list[dict[str, Any]]:
    """Fetch the module index from the danwa-modules GitHub repository.

    Returns all available modules with version, download URL, checksum,
    and (for language packs) translation stats.

    Results are cached server-side for 24 hours; pass ``force_refresh=true``
    to bypass.
    """
    svc = get_module_service()
    try:
        return svc.fetch_repo_index(force_refresh=force_refresh)
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=str(e))


class InstallFromRepoRequest(BaseModel):
    """Request body for installing a module from the danwa-modules repo."""

    module_id: str = Field(..., description="Module ID to install")
    version: str | None = Field(None, description="Specific version (defaults to latest)")


@router.post("/install-from-repo", response_model=dict[str, Any], status_code=201)
def install_module_from_repo(body: InstallFromRepoRequest) -> dict[str, Any]:
    """Install a module directly from the danwa-modules GitHub release.

    Fetches the repo index, resolves the correct version, validates
    dependencies, then downloads and installs the ZIP from GitHub Releases.

    Returns an ``InstallationReport`` with status, files installed, and
    any errors or warnings (including unresolved dependencies).
    """
    svc = get_module_service()
    try:
        report = svc.install_from_repo(body.module_id, version=body.version)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("Failed to install module %s from repo", body.module_id)
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


@router.get("/check-repo-updates", response_model=list[dict[str, Any]])
def check_repo_updates() -> list[dict[str, Any]]:
    """Compare installed module versions against the danwa-modules repo index.

    Uses semver comparison — any remote version strictly greater than the
    installed version is listed as an available update.

    Returns a list of ``{module_id, current_version, available_version,
    download_url, checksum_sha256, name}`` dicts.
    """
    svc = get_module_service()
    try:
        return svc.check_updates()
    except ConnectionError as e:
        raise HTTPException(status_code=502, detail=str(e))


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
        "created_at": str(info.created_at) if info.created_at else None,
        "updated_at": str(info.updated_at) if info.updated_at else None,
        "dependencies": info.dependencies,
        "file_count": info.file_count,
        "profile_preview": info.profile_preview,
    }


@router.get("/{module_id}/profile", response_model=dict[str, Any])
async def get_module_profile(module_id: str) -> dict[str, Any]:
    """Get the parsed profile data for a module, merged with manifest metadata."""
    svc = get_module_service()
    info = svc.get(module_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Module '{module_id}' not found")
    profile = svc.get_profile(module_id) or {}

    manifest = {}
    module_dir = svc._resolve_module_dir(module_id)
    if module_dir:
        manifest_path = module_dir / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                pass

    # Base metadata
    result = {
        "module_id": module_id,
        "name": info.name.get("en", info.name.get(list(info.name.keys())[0]) if info.name else module_id),
        "description": info.description.get("en", info.description.get(list(info.description.keys())[0]) if info.description else ""),
        "role": manifest.get("role", ""),
        "type": info.type if isinstance(info.type, str) else info.type.value,
        "version": info.version,
        "language": info.language,
        "tags": info.tags,
        "profile_type": manifest.get("profile_format", "markdown"),
    }
    # For YAML/JSON profiles, merge the parsed fields (provider, model, etc.)
    # so the edit modal can display them as individual form fields.
    # For markdown profiles, include the raw content string.
    profile_format = manifest.get("profile_format", "markdown")
    if profile_format in ("yaml", "json") and isinstance(profile, dict):
        result.update(profile)
    else:
        result["content"] = profile.get("content", "")
    return result


class ProfileUpdateRequest(BaseModel):
    """ProfileUpdateRequest class."""

    data: dict[str, Any]


@router.put("/{module_id}/profile", response_model=dict[str, Any])
async def update_module_profile(module_id: str, body: ProfileUpdateRequest) -> dict[str, Any]:
    """Update a module's profile data."""
    svc = get_module_service()
    success = svc.update_profile(module_id, body.data)
    if not success:
        raise HTTPException(status_code=404, detail=f"Cannot update profile for module '{module_id}'")
    info = svc.get(module_id)
    return {
        "status": "ok",
        "module_id": module_id,
        "profile": info.profile_preview if info else None,
    }


class DuplicateRequest(BaseModel):
    """DuplicateRequest class."""

    new_id: str = Field(..., description="New module ID")
    new_name: str | None = Field(None, description="Optional new display name")


@router.post("/{module_id}/duplicate", response_model=dict[str, Any], status_code=201)
async def duplicate_module(module_id: str, body: DuplicateRequest) -> dict[str, Any]:
    """Duplicate a module with a new ID."""
    svc = get_module_service()
    result = svc.duplicate_module(module_id, body.new_id, body.new_name)
    if result is None:
        raise HTTPException(status_code=400, detail=f"Cannot duplicate '{module_id}' to '{body.new_id}' (source missing or target exists)")
    return {
        "status": "ok",
        "module_id": result.module_id,
        "name": result.name,
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
    svc = get_module_service()
    module_dir = svc._resolve_module_dir(module_id)
    if not module_dir:
        raise HTTPException(status_code=404, detail=f"Module directory not found: {module_id}")

    manifest_path = module_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail=f"Manifest not found for module '{module_id}'")

    import json

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    module_type = manifest_data.get("type", "")

    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(str(manifest_path), f"{module_id}/manifest.json")

        if module_type == "language-pack":
            # For language packs, generate ui_strings.json from DB
            ui_strings = _export_ui_strings_for_pack(module_id, manifest_data)
            zf.writestr(
                f"{module_id}/ui_strings.json",
                json.dumps(ui_strings, indent=2, ensure_ascii=False),
            )
        else:
            profile_file = manifest_data.get("profile_file")
            if profile_file:
                fpath = module_dir / profile_file
                if fpath.exists():
                    zf.write(str(fpath), f"{module_id}/{profile_file}")
            else:
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


def _export_ui_strings_for_pack(module_id: str, manifest: dict) -> dict[str, str]:
    """Export UI strings for a language-pack module from the database."""
    import sqlite3

    from backend.modules.installer import UI_I18N_DB

    namespace = f"langpack:{module_id}"
    if not UI_I18N_DB.exists():
        return {}

    conn = sqlite3.connect(str(UI_I18N_DB), timeout=10.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT key, value FROM ui_translations WHERE namespace = ?",
            (namespace,),
        )
        return {row["key"]: row["value"] for row in cursor.fetchall()}
    finally:
        conn.close()


# ------------------------------------------------------------------
# Sync DB profiles to module directories
# ------------------------------------------------------------------

_CATEGORY_PREFIX = {
    "llm-profiles": "llm",
    "agents": "agent",
    "role-types": "role",
    "tone-profiles": "tone",
    "workflows": "workflow",
    "workflow-variants": "variant",
    "prompts": "prompt",
}

_TYPE_TO_TABLE = {
    "llm-profile": ("blueprint_llm_profiles", "llm-profiles"),
    "agent-persona": ("agent_personas", "agents"),
    "tone-profile": ("tone_profiles", "tone-profiles"),
    "prompt-variant": ("prompt_templates", "prompts"),
}

_TYPE_TO_FORMAT = {
    "llm-profile": "yaml",
    "agent-persona": "md",
    "tone-profile": "md",
    "prompt-variant": "md",
}

_TYPE_TO_PROFILE_KEYS = {
    "llm-profile": [
        "id",
        "name",
        "provider",
        "model",
        "api_base",
        "api_key_env",
        "max_tokens",
        "context_window",
        "temperature",
        "timeout",
        "cost_per_1k_input",
        "cost_per_1k_output",
        "fallback_llm_profile_id",
        "a2a_endpoint",
        "a2a_timeout",
        "protocol",
        "profile_type",
    ],
}


class SyncFromDbRequest(BaseModel):
    """POST /modules/sync-from-db request body."""

    type: str = Field(..., description="Module type (e.g. 'llm-profile')")
    ids: list[str] | None = Field(None, description="Specific profile IDs to sync (None = all)")


@router.post("/sync-from-db", response_model=dict[str, Any])
def sync_from_db(body: SyncFromDbRequest) -> dict[str, Any]:
    """Export DB profiles as module directories under modules/.

    Reads profiles from the blueprint DB and writes them as module
    directories (manifest.json + profile file).  Used to bridge the
    gap between the Manage views (DB-sourced) and the Modules views
    (filesystem-sourced).
    """
    import sqlite3
    from datetime import UTC, datetime
    from pathlib import Path

    import yaml

    table_info = _TYPE_TO_TABLE.get(body.type)
    if not table_info:
        raise HTTPException(400, f"Unsupported type '{body.type}'. Supported: {list(_TYPE_TO_TABLE)}")

    table_name, category = table_info
    prefix = _CATEGORY_PREFIX.get(category, "mod")
    profile_format = _TYPE_TO_FORMAT.get(body.type, "json")
    profile_keys = _TYPE_TO_PROFILE_KEYS.get(body.type)

    db_path = Path("data/blueprints.db")
    if not db_path.exists():
        raise HTTPException(500, "Blueprints database not found")

    svc = get_module_service()
    modules_dir = svc.modules_dir
    cat_dir = modules_dir / category

    conn = sqlite3.connect(str(db_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        if body.ids:
            placeholders = ",".join("?" for _ in body.ids)
            rows = conn.execute(
                f"SELECT * FROM {table_name} WHERE id IN ({placeholders})",
                body.ids,
            ).fetchall()
        else:
            rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
    finally:
        conn.close()

    exported = 0
    skipped = 0
    errors: list[str] = []
    now = datetime.now(UTC).isoformat()

    for row in rows:
        profile = dict(row)
        profile_id = profile["id"]
        module_id = f"{prefix}-{profile_id}"

        module_dir = cat_dir / module_id
        module_dir.mkdir(parents=True, exist_ok=True)

        # Build profile data (only known keys for llm-profile, full dict otherwise)
        if profile_keys:
            profile_data = {k: profile.get(k) for k in profile_keys if k in profile}
        else:
            # For non-llm types, export the content column or full row
            profile_data = {k: profile[k] for k in profile.keys() if k not in ("created_at", "updated_at")}

        # Write profile file
        profile_file = f"profile.{profile_format}"
        profile_path = module_dir / profile_file
        try:
            if profile_format == "yaml":
                profile_path.write_text(yaml.dump(profile_data, default_flow_style=False, allow_unicode=True), encoding="utf-8")
            elif profile_format == "json":
                profile_path.write_text(json.dumps(profile_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            else:
                # Markdown: use content column
                content = profile.get("content", profile.get("system_prompt", ""))
                profile_path.write_text(content or "", encoding="utf-8")
        except OSError as exc:
            errors.append(f"{profile_id}: failed to write profile: {exc}")
            continue

        # Write manifest.json
        name_val = profile.get("name", module_id)
        desc_val = profile.get("description", "")
        manifest = {
            "schema_version": "3.0.0",
            "module_id": module_id,
            "name": {"en": name_val} if isinstance(name_val, str) else name_val,
            "version": "1.0.0",
            "type": body.type,
            "category": category,
            "author": {"name": "Danwa Community"},
            "license": "CC-BY-4.0",
            "tags": profile.get("tags", []) if isinstance(profile.get("tags"), list) else [],
            "language": profile.get("language", "en") or "en",
            "profile_file": profile_file,
            "profile_format": profile_format,
            "files": [],
            "created_at": now,
            "updated_at": now,
        }
        if desc_val:
            manifest["description"] = {"en": desc_val} if isinstance(desc_val, str) else desc_val

        manifest_path = module_dir / "manifest.json"
        try:
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError as exc:
            errors.append(f"{profile_id}: failed to write manifest: {exc}")
            continue

        exported += 1

    return {
        "exported": exported,
        "skipped": skipped,
        "errors": errors,
        "category": category,
        "module_dir": str(cat_dir),
    }
