"""Case persistence — JSON file-based store.

Each case is stored as a ``case.json`` file inside
``data/tenants/{tenant_id}/cases/{case_id}/``. Thread-safe via locking.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.models.case import Case

logger = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = Path("data") / "tenants"
_DEFAULT_CASE_ID = "_default"


def _normalize_case(data: dict) -> dict:
    """Ensure datetime fields are datetime objects after JSON deserialization."""
    for field in ("created_at", "updated_at"):
        value = data.get(field)
        if isinstance(value, str):
            try:
                data[field] = datetime.fromisoformat(value)
            except (ValueError, TypeError):
                logger.debug("Failed to parse datetime field '%s' in case store", field)
    return data


class CaseStore:
    """Persistent case store using JSON files."""

    def __init__(self, base_dir: Path | str = _DEFAULT_BASE_DIR):
        """Initialise CaseStore."""
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._cache: dict[str, dict[str, Case]] = {}  # tenant_id -> {case_id -> Case}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _tenant_dir(self, tenant_id: str) -> Path:
        """Tenant dir the instance."""
        return self._base_dir / tenant_id / "cases"

    def _case_dir(self, tenant_id: str, case_id: str) -> Path:
        """Case dir the instance."""
        return self._tenant_dir(tenant_id) / case_id

    def _case_json_path(self, tenant_id: str, case_id: str) -> Path:
        """Case json path the instance."""
        return self._case_dir(tenant_id, case_id) / "case.json"

    def _load_tenant(self, tenant_id: str) -> None:
        """Load all cases for a tenant from disk into cache."""
        tenant_cases_dir = self._tenant_dir(tenant_id)
        if not tenant_cases_dir.is_dir():
            self._cache.setdefault(tenant_id, {})
            return
        cases: dict[str, Case] = {}
        for case_dir in sorted(tenant_cases_dir.iterdir()):
            if not case_dir.is_dir():
                continue
            json_path = case_dir / "case.json"
            if not json_path.exists():
                continue
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                data = _normalize_case(data)
                case = Case(**data)
                cases[case.id] = case
            except Exception as exc:
                logger.warning("Failed to load case from %s: %s", json_path, exc)
        self._cache[tenant_id] = cases

    def _get_tenant_cache(self, tenant_id: str) -> dict[str, Case]:
        """Get or load the cache for a given tenant."""
        if tenant_id not in self._cache:
            with self._lock:
                if tenant_id not in self._cache:
                    self._load_tenant(tenant_id)
        return self._cache.get(tenant_id, {})

    def _save_to_disk(self, case: Case) -> None:
        """Persist a single case to disk."""
        case_dir = self._case_dir(case.tenant_id, case.id)
        case_dir.mkdir(parents=True, exist_ok=True)
        json_path = self._case_json_path(case.tenant_id, case.id)
        try:
            json_path.write_text(
                json.dumps(case.model_dump(mode="json"), default=str, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Failed to save case %s: %s", case.id, exc)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(
        self,
        tenant_id: str,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        created_by: str = "",
        case_id: str | None = None,
        is_system: bool = False,
    ) -> Case:
        """Create a new case and persist it."""
        case = Case(
            id=case_id or str(__import__("uuid").uuid4()),
            tenant_id=tenant_id,
            title=title,
            description=description,
            tags=tags or [],
            created_by=created_by,
        )
        with self._lock:
            cache = self._get_tenant_cache(tenant_id)
            cache[case.id] = case
        self._save_to_disk(case)
        # Create subdirectories for debates and dms
        (self._case_dir(tenant_id, case.id) / "debates").mkdir(parents=True, exist_ok=True)
        (self._case_dir(tenant_id, case.id) / "dms").mkdir(parents=True, exist_ok=True)
        logger.info("Created case %s in tenant %s: %s", case.id, tenant_id, title)
        return case

    def get(self, tenant_id: str, case_id: str) -> Case | None:
        """Get a case by tenant and case ID."""
        cache = self._get_tenant_cache(tenant_id)
        return cache.get(case_id)

    def list_by_tenant(self, tenant_id: str) -> list[Case]:
        """List all cases in a tenant, newest first."""
        cache = self._get_tenant_cache(tenant_id)
        return sorted(
            cache.values(),
            key=lambda c: c.created_at,
            reverse=True,
        )

    def update(self, tenant_id: str, case_id: str, **kwargs: Any) -> Case | None:
        """Update case fields and persist."""
        with self._lock:
            cache = self._get_tenant_cache(tenant_id)
            case = cache.get(case_id)
            if not case:
                return None

            for key in ("title", "description", "tags", "status"):
                if key in kwargs and kwargs[key] is not None:
                    setattr(case, key, kwargs[key])

            case.updated_at = datetime.now(UTC)

        self._save_to_disk(case)
        logger.info("Updated case %s in tenant %s", case_id, tenant_id)
        return case

    def delete(self, tenant_id: str, case_id: str) -> bool:
        """Delete/archive a case.

        Returns True if deleted, False if not found.
        Refuses to delete the system default case.
        """
        with self._lock:
            cache = self._get_tenant_cache(tenant_id)
            case = cache.get(case_id)
            if not case:
                return False
            if case_id == _DEFAULT_CASE_ID:
                logger.warning("Cannot delete default case in tenant %s", tenant_id)
                return False
            del cache[case_id]

        case_dir = self._case_dir(tenant_id, case_id)
        try:
            if case_dir.exists():
                import shutil

                shutil.rmtree(case_dir)
                logger.info("Deleted case directory: %s", case_dir)
        except Exception as exc:
            logger.error("Failed to delete case directory %s: %s", case_dir, exc)
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_or_create_default(self, tenant_id: str) -> Case:
        """Get or create the system default case for a tenant."""
        existing = self.get(tenant_id, _DEFAULT_CASE_ID)
        if existing:
            return existing
        return self.create(
            tenant_id=tenant_id,
            title="Default",
            description="System default case",
            case_id=_DEFAULT_CASE_ID,
        )

    def get_case_dir(self, tenant_id: str, case_id: str) -> Path:
        """Get the filesystem directory for a case."""
        return self._case_dir(tenant_id, case_id)

    def count(self, tenant_id: str) -> int:
        """Total number of cases in a tenant."""
        cache = self._get_tenant_cache(tenant_id)
        return len(cache)
