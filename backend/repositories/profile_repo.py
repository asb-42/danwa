"""Profile repository — SQLite storage for active configurations and history."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from backend.core.profiles import ActiveConfiguration

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/profiles.db")
_DEFAULT_PROJECT_ID = "_default"


class ProfileRepository:
    """SQLite-backed storage for active debate configurations."""

    def __init__(self, db_path: Path | str = _DEFAULT_DB_PATH):
        """Initialise ProfileRepository."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Init db the instance."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS active_configurations (
                    debate_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL DEFAULT '_default',
                    llm_profile_id TEXT NOT NULL,
                    agent_personas TEXT NOT NULL,
                    prompt_variant_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    estimated_cost REAL,
                    actual_cost REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS configuration_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    debate_id TEXT NOT NULL,
                    project_id TEXT NOT NULL DEFAULT '_default',
                    llm_profile_id TEXT NOT NULL,
                    agent_personas TEXT NOT NULL,
                    prompt_variant_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    estimated_cost REAL,
                    actual_cost REAL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_active_configs_project
                ON active_configurations (project_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_config_history_project
                ON configuration_history (project_id)
            """)

    def _connect(self) -> sqlite3.Connection:
        """Connect the instance."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Active Configurations
    # ------------------------------------------------------------------

    def save_active_config(self, config: ActiveConfiguration, project_id: str = _DEFAULT_PROJECT_ID) -> None:
        """Save or update an active configuration."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO active_configurations
                    (debate_id, project_id, llm_profile_id, agent_personas,
                     prompt_variant_id, created_at, estimated_cost, actual_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    config.debate_id,
                    project_id,
                    config.llm_profile_id,
                    json.dumps(config.agent_personas),
                    config.prompt_variant_id,
                    config.created_at,
                    config.estimated_cost,
                    config.actual_cost,
                ),
            )
            # Also save to history
            conn.execute(
                """
                INSERT INTO configuration_history
                    (debate_id, project_id, llm_profile_id, agent_personas,
                     prompt_variant_id, created_at, estimated_cost, actual_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    config.debate_id,
                    project_id,
                    config.llm_profile_id,
                    json.dumps(config.agent_personas),
                    config.prompt_variant_id,
                    config.created_at,
                    config.estimated_cost,
                    config.actual_cost,
                ),
            )
        logger.info("Active config saved for debate %s (project=%s)", config.debate_id, project_id)

    def get_active_config(self, debate_id: str) -> ActiveConfiguration | None:
        """Retrieve the active configuration for a debate."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM active_configurations WHERE debate_id = ?",
                (debate_id,),
            ).fetchone()
        if not row:
            return None
        return ActiveConfiguration(
            debate_id=row["debate_id"],
            llm_profile_id=row["llm_profile_id"],
            agent_personas=json.loads(row["agent_personas"]),
            prompt_variant_id=row["prompt_variant_id"],
            created_at=row["created_at"],
            estimated_cost=row["estimated_cost"],
            actual_cost=row["actual_cost"],
        )

    def delete_active_config(self, debate_id: str) -> bool:
        """Delete an active configuration."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM active_configurations WHERE debate_id = ?",
                (debate_id,),
            )
        return cursor.rowcount > 0

    def list_active_configs(self, project_id: str | None = None) -> list[ActiveConfiguration]:
        """List all active configurations, optionally filtered by project."""
        with self._connect() as conn:
            if project_id:
                rows = conn.execute(
                    "SELECT * FROM active_configurations WHERE project_id = ? ORDER BY created_at DESC",
                    (project_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM active_configurations ORDER BY created_at DESC").fetchall()
        return [
            ActiveConfiguration(
                debate_id=row["debate_id"],
                llm_profile_id=row["llm_profile_id"],
                agent_personas=json.loads(row["agent_personas"]),
                prompt_variant_id=row["prompt_variant_id"],
                created_at=row["created_at"],
                estimated_cost=row["estimated_cost"],
                actual_cost=row["actual_cost"],
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_config_history(self, debate_id: str) -> list[ActiveConfiguration]:
        """Get configuration history for a debate."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM configuration_history WHERE debate_id = ? ORDER BY created_at DESC",
                (debate_id,),
            ).fetchall()
        return [
            ActiveConfiguration(
                debate_id=row["debate_id"],
                llm_profile_id=row["llm_profile_id"],
                agent_personas=json.loads(row["agent_personas"]),
                prompt_variant_id=row["prompt_variant_id"],
                created_at=row["created_at"],
                estimated_cost=row["estimated_cost"],
                actual_cost=row["actual_cost"],
            )
            for row in rows
        ]

    def update_actual_cost(self, debate_id: str, actual_cost: float) -> bool:
        """Update the actual cost after a debate completes."""
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE active_configurations SET actual_cost = ? WHERE debate_id = ?",
                (actual_cost, debate_id),
            )
        return cursor.rowcount > 0
