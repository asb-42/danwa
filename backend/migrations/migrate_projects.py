"""Migration: Move existing data into the default project.

This migration is **idempotent** — safe to run on every startup.

Steps:
1. Create the ``_default`` system project if it doesn't exist.
2. Move legacy ``data/debates/*.json`` into ``data/projects/_default/debates/``.
3. Add ``project_id`` column to ``audit_events`` table (if missing).
4. Add ``project_id`` column to ``active_configurations`` and
   ``configuration_history`` tables (if missing).
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_PROJECT_ID = "_default"
_DATA_DIR = Path("data")
_DEBATES_DIR = _DATA_DIR / "debates"
_PROJECTS_DIR = _DATA_DIR / "projects"
_AUDIT_DB = _DATA_DIR / "audit.db"
_PROFILES_DB = _DATA_DIR / "profiles.db"


def migrate_to_projects() -> None:
    """Run all project-related migrations (idempotent)."""
    logger.info("Running project migration...")

    # 1. Ensure default project exists
    _ensure_default_project()

    # 2. Move legacy debates
    _migrate_debates()

    # 3. Add project_id to audit DB
    _migrate_audit_db()

    # 4. Add project_id to profiles DB
    _migrate_profiles_db()

    logger.info("Project migration complete.")


def _ensure_default_project() -> None:
    """Create the _default system project if it doesn't exist."""
    from backend.persistence.project_store import ProjectStore

    store = ProjectStore()
    store.get_or_create_default()
    logger.info("Default project ensured")


def _migrate_debates() -> None:
    """Move legacy debate JSON files into the default project directory."""
    if not _DEBATES_DIR.exists():
        return

    target_dir = _PROJECTS_DIR / _DEFAULT_PROJECT_ID / "debates"
    target_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    for json_file in _DEBATES_DIR.glob("*.json"):
        target = target_dir / json_file.name
        if target.exists():
            # Already migrated
            continue
        shutil.copy2(str(json_file), str(target))
        moved += 1

    if moved > 0:
        logger.info("Migrated %d debate files to default project", moved)

    # Preserve legacy directory structure — do NOT remove (safe copy, not move)
    # Original files remain intact in data/debates/


def _migrate_audit_db() -> None:
    """Add project_id column to audit_events if missing."""
    if not _AUDIT_DB.exists():
        return

    try:
        with sqlite3.connect(str(_AUDIT_DB)) as conn:
            # Check if column already exists
            cursor = conn.execute("PRAGMA table_info(audit_events)")
            columns = {row[1] for row in cursor.fetchall()}

            if "project_id" not in columns:
                conn.execute(
                    f"ALTER TABLE audit_events ADD COLUMN project_id TEXT NOT NULL DEFAULT '{_DEFAULT_PROJECT_ID}'",
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_project ON audit_events (project_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_project_debate ON audit_events (project_id, debate_id)")
                logger.info("Added project_id column to audit_events")
            else:
                logger.debug("audit_events.project_id column already exists")
    except Exception as exc:
        logger.error("Failed to migrate audit DB: %s", exc)


def _migrate_profiles_db() -> None:
    """Add project_id column to profile tables if missing."""
    if not _PROFILES_DB.exists():
        return

    try:
        with sqlite3.connect(str(_PROFILES_DB)) as conn:
            for table in ("active_configurations", "configuration_history"):
                cursor = conn.execute(f"PRAGMA table_info({table})")
                columns = {row[1] for row in cursor.fetchall()}

                if "project_id" not in columns:
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN project_id TEXT NOT NULL DEFAULT '{_DEFAULT_PROJECT_ID}'",
                    )
                    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_project ON {table} (project_id)")
                    logger.info("Added project_id column to %s", table)
                else:
                    logger.debug("%s.project_id column already exists", table)
    except Exception as exc:
        logger.error("Failed to migrate profiles DB: %s", exc)
