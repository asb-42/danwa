"""Base repository with shared SQLite connection management."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from backend.blueprints.migrations import run_migrations

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/blueprints.db")


class BaseRepo:
    """Shared SQLite connection management for all repository mixins."""

    def __init__(self, db_path: Path | str = _DEFAULT_DB_PATH):
        """Initialise BaseRepo."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        run_migrations(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        """Connect the instance."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_table(self, table_name: str, create_sql: str) -> None:
        """Create a table if it does not already exist."""
        with self._connect() as conn:
            conn.execute(create_sql)
        logger.debug("Ensured table %s exists", table_name)
