"""Tag persistence — JSON file-based store.

All tags for a tenant are stored in a single ``tags.json`` file at
``data/tenants/{tenant_id}/tags.json``. Thread-safe via locking.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path

from backend.models.tag import Tag

logger = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = Path("data") / "tenants"


def _normalize_tag(data: dict) -> dict:
    """Ensure datetime fields are datetime objects after JSON deserialization."""
    value = data.get("created_at")
    if isinstance(value, str):
        try:
            data["created_at"] = datetime.fromisoformat(value)
        except (ValueError, TypeError):
            logger.debug("Failed to parse created_at in tag store")
    return data


class TagStore:
    """Persistent tag store using a single JSON file per tenant."""

    def __init__(self, base_dir: Path | str = _DEFAULT_BASE_DIR):
        """Initialise TagStore."""
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._cache: dict[str, dict[str, Tag]] = {}  # tenant_id -> {tag_id -> Tag}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _tags_json_path(self, tenant_id: str) -> Path:
        """Tags json path the instance."""
        return self._base_dir / tenant_id / "tags.json"

    def _load_tenant(self, tenant_id: str) -> dict[str, Tag]:
        """Load tags for a tenant from disk."""
        tags_path = self._tags_json_path(tenant_id)
        if not tags_path.exists():
            return {}
        try:
            data = json.loads(tags_path.read_text(encoding="utf-8"))
            tags = {}
            for item in data:
                item = _normalize_tag(item)
                tag = Tag(**item)
                tags[tag.id] = tag
            return tags
        except Exception as exc:
            logger.warning("Failed to load tags for tenant %s: %s", tenant_id, exc)
            return {}

    def _save_tenant(self, tenant_id: str) -> None:
        """Persist all tags for a tenant to disk."""
        tags = self._cache.get(tenant_id, {})
        tags_path = self._tags_json_path(tenant_id)
        tags_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            tags_path.write_text(
                json.dumps(
                    [t.model_dump(mode="json") for t in tags.values()],
                    default=str,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Failed to save tags for tenant %s: %s", tenant_id, exc)

    def _get_tenant_cache(self, tenant_id: str) -> dict[str, Tag]:
        """Get or load the cache for a given tenant."""
        if tenant_id not in self._cache:
            with self._lock:
                if tenant_id not in self._cache:
                    self._cache[tenant_id] = self._load_tenant(tenant_id)
        return self._cache[tenant_id]

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(self, tenant_id: str, name: str, color: str = "#6366f1", parent_id: str | None = None) -> Tag:
        """Create a new tag for a tenant."""
        tag = Tag(
            tenant_id=tenant_id,
            name=name,
            color=color,
            parent_id=parent_id,
        )
        with self._lock:
            cache = self._get_tenant_cache(tenant_id)
            cache[tag.id] = tag
            self._save_tenant(tenant_id)
        logger.info("Created tag %s in tenant %s: %s", tag.id, tenant_id, name)
        return tag

    def get(self, tenant_id: str, tag_id: str) -> Tag | None:
        """Get a tag by ID within a tenant."""
        cache = self._get_tenant_cache(tenant_id)
        return cache.get(tag_id)

    def list_by_tenant(self, tenant_id: str) -> list[Tag]:
        """List all tags for a tenant, ordered by name."""
        cache = self._get_tenant_cache(tenant_id)
        return sorted(cache.values(), key=lambda t: t.name)

    def update(self, tenant_id: str, tag_id: str, name: str | None = None, color: str | None = None) -> Tag | None:
        """Update a tag's name and/or color."""
        with self._lock:
            cache = self._get_tenant_cache(tenant_id)
            tag = cache.get(tag_id)
            if not tag:
                return None
            if name is not None:
                tag.name = name
            if color is not None:
                tag.color = color
            self._save_tenant(tenant_id)
        return tag

    def delete(self, tenant_id: str, tag_id: str) -> bool:
        """Delete a tag and remove it from all cases that reference it.

        Returns True if deleted, False if not found.
        """
        with self._lock:
            cache = self._get_tenant_cache(tenant_id)
            if tag_id not in cache:
                return False
            del cache[tag_id]
            self._save_tenant(tenant_id)

        # Remove tag from all cases in this tenant
        try:
            from backend.persistence.case_store import CaseStore

            case_store = CaseStore()
            cases = case_store.list_by_tenant(tenant_id)
            for case in cases:
                if tag_id in case.tags:
                    case.tags.remove(tag_id)
                    case_store.update(tenant_id, case.id, tags=case.tags)
                    logger.debug("Removed tag %s from case %s", tag_id, case.id)
        except Exception as exc:
            logger.warning("Failed to clean tag %s from cases: %s", tag_id, exc)

        logger.info("Deleted tag %s from tenant %s", tag_id, tenant_id)
        return True
