"""Workflow definition and workflow template repository methods."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime

from backend.blueprints.workflow_models import (
    ConditionalEdge,
    InterjectionPoint,
    PhaseConfig,
    TemplatePlaceholder,
    TerminationCondition,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    WorkflowTemplate,
)

logger = logging.getLogger(__name__)


class WorkflowRepository:
    """Mixin providing workflow definition and workflow template CRUD."""

    def save_workflow_definition(self, wf: WorkflowDefinition) -> None:
        """Insert or replace a workflow definition."""
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO workflow_definitions
                (id, name, description, canvas_layout_id, execution_order_json,
                 conditional_edges_json, interjection_points_json, node_blueprint_map_json,
                 tags_json, is_active, created_at, updated_at,
                 nodes_json, edges_json, entry_point,
                 termination_conditions_json, version, is_locked, template_id,
                 input_config, phase_configs_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    wf.id,
                    wf.name,
                    wf.description,
                    wf.canvas_layout_id,
                    json.dumps(wf.execution_order),
                    json.dumps([e.model_dump() for e in wf.conditional_edges]),
                    json.dumps([p.model_dump() for p in wf.interjection_points]),
                    json.dumps(wf.node_blueprint_map),
                    json.dumps(wf.tags),
                    int(wf.is_active),
                    wf.created_at.isoformat(),
                    wf.updated_at.isoformat(),
                    json.dumps([n.model_dump() for n in wf.nodes]),
                    json.dumps([e.model_dump() for e in wf.edges]),
                    wf.entry_point,
                    json.dumps([t.model_dump() for t in wf.termination_conditions]),
                    wf.version,
                    int(wf.is_locked),
                    wf.template_id,
                    json.dumps(wf.input_config) if wf.input_config is not None else None,
                    json.dumps({k: v.model_dump() for k, v in wf.phase_configs.items()}) if wf.phase_configs else "{}",
                ),
            )

    def get_workflow_definition(self, wf_id: str) -> WorkflowDefinition | None:
        """Retrieve a workflow definition by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_definitions WHERE id = ?",
                (wf_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_workflow_definition(row)

    def list_workflow_definitions(self, limit: int = 50, offset: int = 0) -> list[WorkflowDefinition]:
        """List all workflow definitions with pagination (deduplicated by name)."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM workflow_definitions
                   WHERE id IN (
                       SELECT id FROM (
                           SELECT id, ROW_NUMBER() OVER (
                               PARTITION BY name ORDER BY created_at DESC
                           ) AS rn FROM workflow_definitions
                       ) WHERE rn = 1
                   )
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
        return [self._row_to_workflow_definition(r) for r in rows]

    def delete_workflow_definition(self, wf_id: str) -> bool:
        """Delete a workflow definition. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM workflow_definitions WHERE id = ?",
                (wf_id,),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_workflow_definition(row: sqlite3.Row) -> WorkflowDefinition:
        """Convert a SQLite row to a WorkflowDefinition model."""
        # New graph columns may be absent if the DB hasn't been migrated yet.
        nodes_json = row["nodes_json"] if "nodes_json" in row.keys() else "[]"
        edges_json = row["edges_json"] if "edges_json" in row.keys() else "[]"
        entry_point = row["entry_point"] if "entry_point" in row.keys() else None
        term_json = row["termination_conditions_json"] if "termination_conditions_json" in row.keys() else "[]"
        version = row["version"] if "version" in row.keys() else 1
        is_locked = row["is_locked"] if "is_locked" in row.keys() else 0
        template_id = row["template_id"] if "template_id" in row.keys() else None
        input_config_raw = row["input_config"] if "input_config" in row.keys() else None
        input_config = json.loads(input_config_raw) if input_config_raw else None

        # Phase configs (may be absent before migration v28)
        phase_configs_raw = row["phase_configs_json"] if "phase_configs_json" in row.keys() else "{}"
        phase_configs_data = json.loads(phase_configs_raw) if phase_configs_raw else {}
        phase_configs = {k: PhaseConfig(**v) for k, v in phase_configs_data.items()}

        return WorkflowDefinition(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            canvas_layout_id=row["canvas_layout_id"],
            execution_order=json.loads(row["execution_order_json"]),
            conditional_edges=[ConditionalEdge(**e) for e in json.loads(row["conditional_edges_json"])],
            interjection_points=[InterjectionPoint(**p) for p in json.loads(row["interjection_points_json"])],
            node_blueprint_map=json.loads(row["node_blueprint_map_json"]),
            tags=json.loads(row["tags_json"]),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            nodes=[WorkflowNode(**n) for n in json.loads(nodes_json)],
            edges=[WorkflowEdge(**e) for e in json.loads(edges_json)],
            entry_point=entry_point,
            termination_conditions=[TerminationCondition(**t) for t in json.loads(term_json)],
            version=version,
            is_locked=bool(is_locked),
            template_id=template_id,
            input_config=input_config,
            phase_configs=phase_configs,
        )

    def save_workflow_template(self, template: WorkflowTemplate) -> None:
        """Insert or replace a workflow template."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO workflow_templates
                    (id, name, description, category, tags_json,
                     template_data_json, placeholders_json,
                     is_system, source_workflow_id,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template.id,
                    template.name,
                    template.description,
                    template.category,
                    json.dumps(template.tags),
                    json.dumps(template.template_data),
                    json.dumps([p.model_dump() for p in template.placeholders]),
                    int(template.is_system),
                    template.source_workflow_id,
                    template.created_at.isoformat(),
                    template.updated_at.isoformat(),
                ),
            )
        logger.debug("Saved workflow template %s", template.id)

    def get_workflow_template(self, template_id: str) -> WorkflowTemplate | None:
        """Retrieve a workflow template by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_templates WHERE id = ?",
                (template_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_workflow_template(row)

    def list_workflow_templates(
        self,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WorkflowTemplate]:
        """List workflow templates, optionally filtered by category."""
        clauses: list[str] = []
        params: list[str] = []
        if category:
            clauses.append("category = ?")
            params.append(category)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM workflow_templates{where} ORDER BY is_system DESC, name LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
        return [self._row_to_workflow_template(r) for r in rows]

    def delete_workflow_template(self, template_id: str) -> bool:
        """Delete a workflow template. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM workflow_templates WHERE id = ?",
                (template_id,),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_workflow_template(row: sqlite3.Row) -> WorkflowTemplate:
        """Convert a SQLite row to a WorkflowTemplate model."""
        return WorkflowTemplate(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            category=row["category"],
            tags=json.loads(row["tags_json"]),
            template_data=json.loads(row["template_data_json"]),
            placeholders=[TemplatePlaceholder(**p) for p in json.loads(row["placeholders_json"])],
            is_system=bool(row["is_system"]),
            source_workflow_id=row["source_workflow_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
