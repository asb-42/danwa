"""Role definition and role type repository methods."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime

from backend.blueprints.models import RoleDefinition, RoleType

logger = logging.getLogger(__name__)


class RoleRepository:
    """Mixin providing role definition and role type CRUD."""

    def save_role_definition(self, role_def: RoleDefinition) -> None:
        """Insert or replace a role definition."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO role_definitions
                    (id, name, role, role_type_id, description, argumentation_pattern, mode,
                     prompt_template_id,
                     max_rounds, consensus_threshold, tags_json,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    role_def.id,
                    role_def.name,
                    role_def.role_type_id.split("-")[0] if role_def.role_type_id else "strategist",
                    role_def.role_type_id,
                    role_def.description,
                    role_def.argumentation_pattern,
                    role_def.mode,
                    role_def.prompt_template_id,
                    role_def.max_rounds,
                    role_def.consensus_threshold,
                    json.dumps(role_def.tags),
                    role_def.created_at.isoformat(),
                    role_def.updated_at.isoformat(),
                ),
            )
        logger.debug("Saved role definition %s", role_def.id)

    def get_role_definition(self, role_id: str) -> RoleDefinition | None:
        """Retrieve a role definition by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM role_definitions WHERE id = ?",
                (role_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_role_definition(row)

    def list_role_definitions(
        self,
        role: str | None = None,
        argumentation_pattern: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RoleDefinition]:
        """List role definitions, optionally filtered by role type."""
        clauses: list[str] = []
        params: list[str] = []
        if role:
            clauses.append("role_type_id = ?")
            params.append(role)
        if argumentation_pattern:
            clauses.append("argumentation_pattern = ?")
            params.append(argumentation_pattern)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM role_definitions{where} ORDER BY role_type_id, name LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
        return [self._row_to_role_definition(r) for r in rows]

    def delete_role_definition(self, role_id: str) -> bool:
        """Delete a role definition. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM role_definitions WHERE id = ?",
                (role_id,),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_role_definition(row: sqlite3.Row) -> RoleDefinition:
        return RoleDefinition(
            id=row["id"],
            name=row["name"],
            role_type_id=row["role_type_id"] if "role_type_id" in row.keys() else row["role"],
            description=row["description"],
            argumentation_pattern=row["argumentation_pattern"] if "argumentation_pattern" in row.keys() else None,
            mode=row["mode"] if "mode" in row.keys() else None,
            prompt_template_id=row["prompt_template_id"],
            max_rounds=row["max_rounds"],
            consensus_threshold=row["consensus_threshold"],
            tags=json.loads(row["tags_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def save_role_type(self, role_type: RoleType) -> None:
        """Insert or replace a role type."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO role_types
                    (id, name, description, icon, color,
                     default_max_rounds, default_consensus_threshold,
                     category,
                     tags_json, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    role_type.id,
                    role_type.name,
                    role_type.description,
                    role_type.icon,
                    role_type.color,
                    role_type.default_max_rounds,
                    role_type.default_consensus_threshold,
                    role_type.category,
                    json.dumps(role_type.tags),
                    int(role_type.is_active),
                    role_type.created_at.isoformat(),
                    role_type.updated_at.isoformat(),
                ),
            )

    def get_role_type(self, role_type_id: str) -> RoleType | None:
        """Retrieve a role type by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM role_types WHERE id = ?", (role_type_id,)).fetchone()
        return self._row_to_role_type(row) if row else None

    def list_role_types(self, limit: int = 100, offset: int = 0, active_only: bool = False) -> list[RoleType]:
        """List role types with pagination."""
        with self._connect() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM role_types WHERE is_active = 1 ORDER BY name LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM role_types ORDER BY name LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        return [self._row_to_role_type(r) for r in rows]

    def delete_role_type(self, role_type_id: str) -> bool:
        """Delete a role type. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM role_types WHERE id = ?", (role_type_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_role_type(row: sqlite3.Row) -> RoleType:
        """Convert a SQLite row to a RoleType model."""
        return RoleType(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            icon=row["icon"],
            color=row["color"],
            default_max_rounds=row["default_max_rounds"],
            default_consensus_threshold=row["default_consensus_threshold"],
            category=row["category"] if "category" in row.keys() else "functional",
            tags=json.loads(row["tags_json"]),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
