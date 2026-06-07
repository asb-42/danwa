"""Project persistence — JSON file-based store.

Each project is stored as a ``project.json`` file inside
``data/tenants/{tenant_id}/cases/{project_id}/``.
Thread-safe via locking.

Backward-compatible: also scans old ``data/projects/{project_id}/`` on startup.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.models.project import Project, ProjectConfig

logger = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = Path("data")
_OLD_BASE_DIR = Path("data/projects")
_DEFAULT_PROJECT_ID = "_default"


def _normalize_project(data: dict) -> dict:
    """Ensure datetime fields are datetime objects after JSON deserialization."""
    for field in ("created_at", "updated_at"):
        value = data.get(field)
        if isinstance(value, str):
            try:
                data[field] = datetime.fromisoformat(value)
            except (ValueError, TypeError) as e:
                logger.debug("Failed to parse datetime field '%s' in project store: %s", field, e)
    return data


class ProjectStore:
    """Persistent project store using JSON files."""

    def __init__(self, base_dir: Path | str = _DEFAULT_BASE_DIR):
        """Initialise ProjectStore."""
        if isinstance(base_dir, str):
            base_dir = Path(base_dir)
        # When using the default base, scope under tenants/ for the new structure.
        # Custom base_dir (e.g. from tests) is used as-is.
        if base_dir == _DEFAULT_BASE_DIR:
            self._base_dir = base_dir / "tenants"
        else:
            self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._cache: dict[str, Project] = {}
        self._load_all()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _tenant_dir(self, tenant_id: str) -> Path:
        """Tenant dir the instance."""
        return self._base_dir / tenant_id / "cases"

    def _project_dir_for(self, tenant_id: str, project_id: str) -> Path:
        """Project dir for the instance."""
        return self._tenant_dir(tenant_id) / project_id

    def _project_json_path(self, tenant_id: str, project_id: str) -> Path:
        """Project json path the instance."""
        return self._project_dir_for(tenant_id, project_id) / "project.json"

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        """Load all projects from disk into memory.

        Scans the new tenant-cased structure first (``data/tenants/*/cases/*/``),
        then falls back to the old structure (``data/projects/*/``) for
        backward compatibility during migration.
        """
        with self._lock:
            # 1. New structure: data/tenants/{tid}/cases/{cid}/
            for tenant_dir in sorted(self._base_dir.iterdir()):
                if not tenant_dir.is_dir():
                    continue
                cases_dir = tenant_dir / "cases"
                if not cases_dir.is_dir():
                    continue
                for case_dir in sorted(cases_dir.iterdir()):
                    if not case_dir.is_dir():
                        continue
                    self._load_project_from_dir(case_dir)

            # 2. Old structure (backward compat): data/projects/{pid}/
            # Only scan the legacy path when using the default base dir
            default_tenants_dir = _DEFAULT_BASE_DIR / "tenants"
            if self._base_dir == default_tenants_dir:
                old_base = Path("data/projects")
                if old_base.is_dir():
                    for project_dir in sorted(old_base.iterdir()):
                        if not project_dir.is_dir():
                            continue
                        # Skip if already loaded from new structure
                        json_path = project_dir / "project.json"
                        if not json_path.exists():
                            continue
                        try:
                            data = json.loads(json_path.read_text(encoding="utf-8"))
                            data = _normalize_project(data)
                            if data.get("id") in self._cache:
                                continue
                            project = Project(**data)
                            self._cache[project.id] = project
                        except Exception as exc:
                            logger.warning("Failed to load project from %s: %s", json_path, exc)

            logger.info("Loaded %d projects from tenant-cased + legacy paths", len(self._cache))

    def _load_project_from_dir(self, case_dir: Path) -> None:
        """Load a single project from a ``project.json`` in the given directory."""
        json_path = case_dir / "project.json"
        if not json_path.exists():
            return
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            data = _normalize_project(data)
            project = Project(**data)
            self._cache[project.id] = project
        except Exception as exc:
            logger.warning("Failed to load project from %s: %s", json_path, exc)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_to_disk(self, project: Project) -> None:
        """Persist a single project to disk in the tenant-cased path."""
        project_dir = self._project_dir_for(project.tenant_id, project.id)
        project_dir.mkdir(parents=True, exist_ok=True)
        json_path = self._project_json_path(project.tenant_id, project.id)
        try:
            json_path.write_text(
                json.dumps(project.model_dump(mode="json"), default=str, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Failed to save project %s: %s", project.id, exc)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(
        self,
        name: str,
        description: str = "",
        is_system: bool = False,
        project_id: str | None = None,
        tenant_id: str = "_default",
    ) -> Project:
        """Create a new project and persist it."""
        project = Project(
            id=project_id or str(__import__("uuid").uuid4()),
            name=name,
            description=description,
            is_system=is_system,
            tenant_id=tenant_id,
        )
        with self._lock:
            self._cache[project.id] = project
        self._save_to_disk(project)
        # Create subdirectories for debates and dms
        project_dir = self._project_dir_for(tenant_id, project.id)
        (project_dir / "debates").mkdir(parents=True, exist_ok=True)
        (project_dir / "dms").mkdir(parents=True, exist_ok=True)
        logger.info("Created project %s: %s", project.id, name)
        return project

    def get(self, project_id: str) -> Project | None:
        """Get a project by ID."""
        return self._cache.get(project_id)

    def list_all(self) -> list[Project]:
        """List all projects, newest first."""
        return sorted(
            self._cache.values(),
            key=lambda p: p.created_at,
            reverse=True,
        )

    def list_by_tenant(self, tenant_id: str) -> list[Project]:
        """List projects belonging to a specific tenant, newest first."""
        return sorted(
            [p for p in self._cache.values() if p.tenant_id == tenant_id],
            key=lambda p: p.created_at,
            reverse=True,
        )

    def update(self, project_id: str, **kwargs: Any) -> Project | None:
        """Update project fields and persist."""
        with self._lock:
            project = self._cache.get(project_id)
            if not project:
                return None

            if "name" in kwargs and kwargs["name"] is not None:
                project.name = kwargs["name"]
            if "description" in kwargs and kwargs["description"] is not None:
                project.description = kwargs["description"]

            if "config" in kwargs and kwargs["config"] is not None:
                new_config = kwargs["config"]
                if isinstance(new_config, ProjectConfig):
                    project.config = new_config
                elif isinstance(new_config, dict):
                    project.config = ProjectConfig(**new_config)

            project.updated_at = datetime.now(UTC)

        self._save_to_disk(project)
        logger.info("Updated project %s", project_id)
        return project

    def delete(self, project_id: str) -> bool:
        """Delete a project.

        Returns True if deleted, False if not found.
        Refuses to delete system projects.
        """
        with self._lock:
            project = self._cache.get(project_id)
            if not project:
                return False
            if project.is_system:
                logger.warning("Cannot delete system project %s", project_id)
                return False
            del self._cache[project_id]

        project_dir = self._project_dir_for(project.tenant_id, project.id)
        try:
            if project_dir.exists():
                import shutil

                shutil.rmtree(project_dir)
                logger.info("Deleted project directory: %s", project_dir)
        except Exception as exc:
            logger.error("Failed to delete project directory %s: %s", project_dir, exc)
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_or_create_default(self) -> Project:
        """Get or create the system default project."""
        existing = self.get(_DEFAULT_PROJECT_ID)
        if existing:
            return existing
        return self.create(
            name="Default",
            description="System default project — created during migration",
            is_system=True,
            project_id=_DEFAULT_PROJECT_ID,
        )

    def get_project_dir(self, project_id: str) -> Path:
        """Get the filesystem directory for a project.

        Looks up the project's tenant from the in-memory cache to
        resolve the correct path under ``data/tenants/{tid}/cases/{pid}/``.
        """
        project = self._cache.get(project_id)
        if project:
            return self._project_dir_for(project.tenant_id, project_id)
        # Fallback for migration: construct path from old structure
        # (only when using the default base dir)
        default_tenants_dir = _DEFAULT_BASE_DIR / "tenants"
        if self._base_dir == default_tenants_dir:
            return _OLD_BASE_DIR / project_id
        raise FileNotFoundError(f"Project {project_id} not found in cache")

    def count(self) -> int:
        """Total number of projects."""
        return len(self._cache)
