"""Migration v002: Move projects from ``data/projects/`` to tenant-cased paths.

This migration is **idempotent** — safe to run on every startup.

Before: ``data/projects/{project_id}/project.json`` (flat, single-tenant)
After:  ``data/tenants/{tenant_id}/cases/{project_id}/project.json``

Steps:
1. Skip if marker ``data/projects/.moved_to_tenant_cases`` exists.
2. For each project directory under ``data/projects/``:
   a. Read ``project.json`` to determine ``tenant_id`` (default: ``_default``).
   b. Create target ``data/tenants/{tenant_id}/cases/{project_id}/``.
   c. Move the entire directory contents (project.json + debates/ + dms/ + …).
3. Create marker file in ``data/projects/``.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path("data")
_OLD_PROJECTS_DIR = _DATA_DIR / "projects"
_MARKER_FILE = ".moved_to_tenant_cases"
_DEFAULT_TENANT_ID = "_default"


def migrate_to_case_paths() -> None:
    """Move all projects from ``data/projects/`` to tenant-cased paths."""
    logger.info("Running v002 case-path migration…")

    if not _OLD_PROJECTS_DIR.is_dir():
        logger.debug("No legacy projects directory found — skipping")
        return

    marker = _OLD_PROJECTS_DIR / _MARKER_FILE
    if marker.exists():
        logger.debug("v002 migration already completed (marker exists)")
        return

    tenants_dir = _DATA_DIR / "tenants"
    tenants_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    skipped = 0
    for project_dir in sorted(_OLD_PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir():
            continue

        project_id = project_dir.name

        # Read tenant_id from project.json (fall back to _default)
        tenant_id = _resolve_tenant_id(project_dir, project_id)

        target_dir = tenants_dir / tenant_id / "cases" / project_id
        _move_project_dir(project_dir, target_dir, project_id, tenant_id)
        moved += 1

    # Write marker so we skip on future startups
    marker.write_text(
        json.dumps(
            {
                "migrated_at": __import__("datetime")
                .datetime.now(
                    __import__("datetime").timezone.utc,
                )
                .isoformat(),
                "projects_moved": moved,
                "projects_skipped": skipped,
            },
            default=str,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("v002 migration complete: %d projects moved, %d skipped", moved, skipped)


def _resolve_tenant_id(project_dir: Path, project_id: str) -> str:
    """Read tenant_id from project.json, defaulting to ``_default``."""
    json_path = project_dir / "project.json"
    if not json_path.exists():
        logger.debug("No project.json in %s — using tenant=_default", project_dir)
        return _DEFAULT_TENANT_ID

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        tid = data.get("tenant_id", _DEFAULT_TENANT_ID)
        if not isinstance(tid, str) or not tid.strip():
            return _DEFAULT_TENANT_ID
        return tid.strip()
    except Exception as exc:
        logger.warning("Failed to read tenant_id from %s: %s — using _default", json_path, exc)
        return _DEFAULT_TENANT_ID


def _move_project_dir(
    src: Path,
    dst: Path,
    project_id: str,
    tenant_id: str,
) -> None:
    """Move a single project directory from old to new location.

    If the target already exists, merge contents (new wins on conflict)
    rather than overwriting.
    """
    if dst.exists():
        logger.debug("Target %s already exists — merging contents", dst)
        _merge_dirs(src, dst)
        # Remove source after merge
        shutil.rmtree(src)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

    logger.info("Moved project %s → %s (tenant=%s)", project_id, dst, tenant_id)


def _merge_dirs(src: Path, dst: Path) -> None:
    """Recursively merge ``src`` into ``dst`` (new wins on file conflict)."""
    for item in src.iterdir():
        item_dst = dst / item.name
        if item.is_dir():
            if item_dst.exists():
                _merge_dirs(item, item_dst)
            else:
                shutil.move(str(item), str(item_dst))
        else:
            # File: overwrite destination
            shutil.move(str(item), str(item_dst))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate_to_case_paths()
