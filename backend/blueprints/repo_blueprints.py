"""Agent blueprint, canvas layout, and bundle repository methods."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime

from backend.blueprints.models import (
    AgentBlueprint,
    AgentBundle,
    BundleComposition,
    CanvasLayout,
    CanvasLayoutData,
)

logger = logging.getLogger(__name__)


class BlueprintRepo:
    """Mixin providing agent blueprint, canvas layout, and bundle CRUD."""

    def save_blueprint(self, blueprint: AgentBlueprint) -> None:
        """Insert or replace an agent blueprint."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_blueprints
                    (id, name, description, llm_profile_id,
                     role_definition_id, prompt_template_id,
                     tts_voice_id,
                     tags_json, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    blueprint.id,
                    blueprint.name,
                    blueprint.description,
                    blueprint.llm_profile_id,
                    blueprint.role_definition_id,
                    None,  # prompt_template_id removed from model
                    blueprint.tts_voice_id,
                    json.dumps(blueprint.tags),
                    int(blueprint.is_active),
                    blueprint.created_at.isoformat(),
                    blueprint.updated_at.isoformat(),
                ),
            )
        logger.debug("Saved agent blueprint %s", blueprint.id)

    def get_blueprint(self, blueprint_id: str) -> AgentBlueprint | None:
        """Retrieve an agent blueprint by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_blueprints WHERE id = ?",
                (blueprint_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_blueprint(row)

    def list_blueprints(
        self,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AgentBlueprint]:
        """List agent blueprints, optionally filtering to active only."""
        where = " WHERE is_active = 1" if active_only else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM agent_blueprints{where} ORDER BY name LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._row_to_blueprint(r) for r in rows]

    def delete_blueprint(self, blueprint_id: str) -> bool:
        """Delete an agent blueprint. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_blueprints WHERE id = ?",
                (blueprint_id,),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_blueprint(row: sqlite3.Row) -> AgentBlueprint:
        # Graceful fallback for tts_voice_id (may not exist in older DBs)
        """Row to blueprint the instance."""
        tts_voice_id = None
        if "tts_voice_id" in row.keys():
            tts_voice_id = row["tts_voice_id"]
        return AgentBlueprint(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            llm_profile_id=row["llm_profile_id"],
            role_definition_id=row["role_definition_id"],
            tts_voice_id=tts_voice_id,
            tags=json.loads(row["tags_json"]),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def save_layout(self, layout: CanvasLayout) -> None:
        """Insert or replace a canvas layout."""
        layout_json = layout.layout_data.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO canvas_layouts
                    (id, name, description, project_id, layout_json,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    layout.id,
                    layout.name,
                    layout.description,
                    layout.project_id,
                    layout_json,
                    layout.created_at.isoformat(),
                    layout.updated_at.isoformat(),
                ),
            )
        logger.debug("Saved canvas layout %s", layout.id)

    def get_layout(self, layout_id: str) -> CanvasLayout | None:
        """Retrieve a canvas layout by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM canvas_layouts WHERE id = ?",
                (layout_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_layout(row)

    def list_layouts(
        self,
        project_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CanvasLayout]:
        """List canvas layouts, optionally filtered by project."""
        clauses: list[str] = []
        params: list[str] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM canvas_layouts{where} ORDER BY name LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
        return [self._row_to_layout(r) for r in rows]

    def delete_layout(self, layout_id: str) -> bool:
        """Delete a canvas layout. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM canvas_layouts WHERE id = ?",
                (layout_id,),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_layout(row: sqlite3.Row) -> CanvasLayout:
        """Row to layout the instance."""
        layout_data = CanvasLayoutData.model_validate_json(row["layout_json"])
        return CanvasLayout(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            project_id=row["project_id"],
            layout_data=layout_data,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def save_bundle(self, bundle: AgentBundle) -> None:
        """Insert or replace an agent bundle."""
        composition_json = json.dumps(bundle.composition.model_dump()) if bundle.composition else None
        model_params_json = json.dumps(bundle.model_params) if bundle.model_params else "{}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_bundles
                    (id, name, description, llm_profile_id, role_type_id,
                     role_definition_id, prompt_template_id, tone_profile_id,
                     persona_id, tags_json, is_active, created_at, updated_at,
                     composition_json, model_params_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bundle.id,
                    bundle.name,
                    bundle.description,
                    bundle.llm_profile_id,
                    bundle.role_type_id,
                    None,  # role_definition_id removed from model
                    None,  # prompt_template_id removed from model
                    bundle.tone_profile_id,
                    None,  # persona_id removed from model
                    json.dumps(bundle.tags),
                    int(bundle.is_active),
                    bundle.created_at.isoformat(),
                    bundle.updated_at.isoformat(),
                    composition_json,
                    model_params_json,
                ),
            )
        logger.debug("Saved agent bundle %s", bundle.id)

    def get_bundle(self, bundle_id: str) -> AgentBundle | None:
        """Retrieve an agent bundle by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_bundles WHERE id = ?",
                (bundle_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_bundle(row)

    def list_bundles(
        self,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AgentBundle]:
        """List agent bundles, optionally filtering to active only."""
        where = " WHERE is_active = 1" if active_only else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM agent_bundles{where} ORDER BY name LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._row_to_bundle(r) for r in rows]

    def delete_bundle(self, bundle_id: str) -> bool:
        """Delete an agent bundle. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_bundles WHERE id = ?",
                (bundle_id,),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_bundle(row: sqlite3.Row) -> AgentBundle:
        """Convert a SQLite row to an AgentBundle model."""
        composition = None
        composition_raw = row["composition_json"] if "composition_json" in row.keys() else None
        if composition_raw:
            try:
                parsed = json.loads(composition_raw)
                if parsed:
                    composition = BundleComposition(**parsed)
            except (json.JSONDecodeError, TypeError):
                logger.debug("Failed to parse composition_json for bundle %s", row["id"])
        model_params = {}
        model_params_raw = row["model_params_json"] if "model_params_json" in row.keys() else None
        if model_params_raw:
            try:
                parsed = json.loads(model_params_raw)
                if parsed and isinstance(parsed, dict):
                    model_params = parsed
            except (json.JSONDecodeError, TypeError):
                logger.debug("Failed to parse model_params_json for bundle %s", row["id"])
        return AgentBundle(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            llm_profile_id=row["llm_profile_id"],
            role_type_id=row["role_type_id"],
            tone_profile_id=row["tone_profile_id"],
            tags=json.loads(row["tags_json"]),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            composition=composition,
            model_params=model_params,
        )
