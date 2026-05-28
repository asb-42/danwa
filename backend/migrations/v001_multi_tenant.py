"""Migration v001: Single-user to multi-tenant upgrade.

This migration is **idempotent** — safe to run on every startup.

Steps:
1. Ensure the ``_default`` tenant exists in auth.db.
2. Ensure the ``_default`` project has ``tenant_id = '_default'``.
3. Add ``tenant_id`` column to projects table (JSON files) if missing.
4. Ensure admin user exists (delegated to seed).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_TENANT_ID = "_default"
_DATA_DIR = Path("data")
_PROJECTS_DIR = _DATA_DIR / "projects"
_AUTH_DB = _DATA_DIR / "auth.db"


def migrate_to_multi_tenant() -> None:
    """Run all multi-tenant migrations (idempotent)."""
    logger.info("Running multi-tenant migration...")

    # 1. Ensure default tenant exists
    _ensure_default_tenant()

    # 2. Ensure all existing projects have tenant_id
    _migrate_project_tenant_ids()

    # 3. Ensure default project exists
    _ensure_default_project()

    logger.info("Multi-tenant migration complete.")


def _ensure_default_tenant() -> None:
    """Create the _default tenant if it doesn't exist."""
    from backend.persistence.tenant_store import TenantStore

    store = TenantStore()
    existing = store.get(_DEFAULT_TENANT_ID)
    if existing:
        logger.debug("Default tenant already exists")
        return

    store.create(name="Default", plan="free", tenant_id=_DEFAULT_TENANT_ID)
    logger.info("Created default tenant (_default)")


def _migrate_project_tenant_ids() -> None:
    """Add tenant_id to all existing project.json files that don't have it."""
    if not _PROJECTS_DIR.exists():
        return

    migrated = 0
    for project_dir in _PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        json_path = project_dir / "project.json"
        if not json_path.exists():
            continue

        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if "tenant_id" not in data:
                data["tenant_id"] = _DEFAULT_TENANT_ID
                json_path.write_text(
                    json.dumps(data, default=str, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                migrated += 1
        except Exception as exc:
            logger.warning("Failed to migrate project %s: %s", project_dir.name, exc)

    if migrated > 0:
        logger.info("Added tenant_id to %d project files", migrated)
    else:
        logger.debug("All projects already have tenant_id")


def _ensure_default_project() -> None:
    """Ensure the _default project exists and has tenant_id."""
    from backend.persistence.project_store import ProjectStore

    store = ProjectStore()
    project = store.get("_default")
    if project:
        # Ensure tenant_id is set
        if not project.tenant_id:
            store.update("_default", tenant_id=_DEFAULT_TENANT_ID)
            logger.info("Set tenant_id on default project")
        return

    store.create(
        name="Default",
        description="System default project — created during migration",
        is_system=True,
        project_id="_default",
        tenant_id=_DEFAULT_TENANT_ID,
    )
    logger.info("Created default project (_default)")
