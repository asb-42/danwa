"""UserKeyStore — per-user LLM API key overrides (BYOK).

Stores user-scoped API keys in the auth.db database.
Keys are stored as plaintext for simplicity — in production,
use application-level encryption (e.g., Fernet) before storage.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/auth.db")


class UserKeyStore:
    """CRUD operations for user-scoped LLM API keys."""

    def __init__(self, db_path: Path | str | None = None):
        """Initialise UserKeyStore."""
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self) -> None:
        """Init db the instance."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_llm_keys (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                profile_id TEXT NOT NULL,
                api_key TEXT NOT NULL,
                label TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, profile_id)
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_user_keys_user ON user_llm_keys(user_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_user_keys_profile ON user_llm_keys(profile_id)")
        self.conn.commit()

    def set_key(self, user_id: str, profile_id: str, api_key: str, label: str = "") -> None:
        """Store or update an API key for a user+profile combination."""

        now = datetime.now(UTC).isoformat()
        key_id = f"{user_id}:{profile_id}"
        self.conn.execute(
            """INSERT INTO user_llm_keys (id, user_id, profile_id, api_key, label, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, profile_id) DO UPDATE SET
                api_key = excluded.api_key,
                label = excluded.label,
                updated_at = excluded.updated_at""",
            (key_id, user_id, profile_id, api_key, label, now, now),
        )
        self.conn.commit()
        logger.info("Stored BYOK key for user %s, profile %s", user_id, profile_id)

    def get_key(self, user_id: str, profile_id: str) -> str | None:
        """Retrieve an API key for a user+profile. Returns None if not set."""
        cursor = self.conn.execute(
            "SELECT api_key FROM user_llm_keys WHERE user_id = ? AND profile_id = ?",
            (user_id, profile_id),
        )
        row = cursor.fetchone()
        return row["api_key"] if row else None

    def list_keys(self, user_id: str) -> list[dict]:
        """List all API keys for a user (keys are masked in the response)."""
        cursor = self.conn.execute(
            "SELECT profile_id, label, created_at, updated_at FROM user_llm_keys WHERE user_id = ?",
            (user_id,),
        )
        return [
            {
                "profile_id": row["profile_id"],
                "label": row["label"],
                "has_key": True,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in cursor.fetchall()
        ]

    def delete_key(self, user_id: str, profile_id: str) -> bool:
        """Delete an API key for a user+profile. Returns True if deleted."""
        self.conn.execute(
            "DELETE FROM user_llm_keys WHERE user_id = ? AND profile_id = ?",
            (user_id, profile_id),
        )
        self.conn.commit()
        return True

    def delete_all_keys(self, user_id: str) -> int:
        """Delete all API keys for a user. Returns count of deleted keys."""
        cursor = self.conn.execute("DELETE FROM user_llm_keys WHERE user_id = ?", (user_id,))
        self.conn.commit()
        return cursor.rowcount
