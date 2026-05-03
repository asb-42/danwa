"""Debate persistence — JSON file-based store.

Stores debates as individual JSON files in a data directory.
Survives server restarts. Thread-safe via file locking.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.models.schemas import DebateStatus

logger = logging.getLogger(__name__)

_DEFAULT_DATA_DIR = Path("data/debates")


def _normalize_debate(data: dict) -> dict:
    """Ensure status is a DebateStatus enum (may be a plain string after JSON load)."""
    status = data.get("status")
    if isinstance(status, str):
        try:
            data["status"] = DebateStatus(status)
        except ValueError:
            pass
    return data


class DebateStore:
    """Persistent debate store using JSON files."""

    def __init__(self, data_dir: Path | str = _DEFAULT_DATA_DIR):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # In-memory cache for fast access
        self._cache: Dict[str, dict] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load all debates from disk into memory."""
        with self._lock:
            for path in self._data_dir.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    debate_id = data.get("debate_id")
                    if debate_id:
                        self._cache[debate_id] = _normalize_debate(data)
                except Exception as exc:
                    logger.warning("Failed to load debate %s: %s", path.name, exc)
            logger.info("Loaded %d debates from %s", len(self._cache), self._data_dir)

    def _save_to_disk(self, debate_id: str) -> None:
        """Persist a single debate to disk."""
        data = self._cache.get(debate_id)
        if not data:
            return
        path = self._data_dir / f"{debate_id}.json"
        try:
            # Build a JSON-safe copy: convert Pydantic models and enums
            serializable = {}
            for key, value in data.items():
                if hasattr(value, "model_dump"):
                    serializable[key] = value.model_dump(mode="json")
                elif hasattr(value, "value"):  # StrEnum
                    serializable[key] = value.value
                else:
                    serializable[key] = value
            path.write_text(json.dumps(serializable, default=str, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("Failed to save debate %s: %s", debate_id, exc)

    def put(self, debate_id: str, debate: dict) -> None:
        """Store a debate (in memory + on disk)."""
        with self._lock:
            self._cache[debate_id] = debate
        self._save_to_disk(debate_id)

    def get(self, debate_id: str) -> Optional[dict]:
        """Get a debate by ID."""
        return self._cache.get(debate_id)

    def list_all(self, limit: int = 50, offset: int = 0) -> List[dict]:
        """List all debates, newest first."""
        debates = sorted(
            self._cache.values(),
            key=lambda d: d.get("created_at", ""),
            reverse=True,
        )
        return debates[offset:offset + limit]

    def count(self) -> int:
        """Total number of debates."""
        return len(self._cache)

    def update(self, debate_id: str, **kwargs: Any) -> Optional[dict]:
        """Update fields of a debate and persist."""
        with self._lock:
            debate = self._cache.get(debate_id)
            if not debate:
                return None
            debate.update(kwargs)
        self._save_to_disk(debate_id)
        return debate
