"""Blueprint Canvas — SQLite repository for blueprints and canvas layouts.

Follows the pattern of ``backend.repositories.profile_repo.ProfileRepository``
— SQLite connection per operation, ``row_factory = sqlite3.Row``.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from backend.blueprints.migrations import run_migrations
from backend.blueprints.models import (
    AgentBlueprint,
    AgentBundle,
    BlueprintLLMProfile,
    CanvasLayout,
    CanvasLayoutData,
    PromptTemplate,
    RoleDefinition,
    RoleType,
    ToneProfile,
)
from backend.blueprints.workflow_models import (
    ConditionalEdge,
    InterjectionPoint,
    TemplatePlaceholder,
    TerminationCondition,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    WorkflowTemplate,
)

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/blueprints.db")


class BlueprintRepository:
    """SQLite-backed storage for Agent Blueprints and Canvas Layouts."""

    def __init__(self, db_path: Path | str = _DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        run_migrations(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ------------------------------------------------------------------
    # LLM Profiles
    # ------------------------------------------------------------------

    def save_llm_profile(self, profile: BlueprintLLMProfile) -> None:
        """Insert or replace an LLM profile."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO blueprint_llm_profiles
                    (id, name, profile_type, provider, model, api_base, api_key_env,
                     max_tokens, context_window, temperature, timeout,
                     cost_per_1k_input, cost_per_1k_output,
                     description, tags_json, created_at, updated_at,
                     protocol, a2a_endpoint, a2a_timeout,
                     fallback_llm_profile_id, a2a_config_json,
                      service_eligible)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.id,
                    profile.name,
                    profile.profile_type,
                    profile.provider,
                    profile.model,
                    profile.api_base,
                    profile.api_key_env,
                    profile.max_tokens,
                    profile.context_window,
                    profile.temperature,
                    profile.timeout,
                    profile.cost_per_1k_input,
                    profile.cost_per_1k_output,
                    profile.description,
                    json.dumps(profile.tags),
                    profile.created_at.isoformat(),
                    profile.updated_at.isoformat(),
                    profile.protocol,
                    profile.a2a_endpoint,
                    profile.a2a_timeout,
                    profile.fallback_llm_profile_id,
                    json.dumps(profile.a2a_config),
                    profile.service_eligible,
                ),
            )
        logger.debug("Saved LLM profile %s", profile.id)

    def get_llm_profile(self, profile_id: str) -> BlueprintLLMProfile | None:
        """Retrieve an LLM profile by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM blueprint_llm_profiles WHERE id = ?",
                (profile_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_llm_profile(row)

    def list_llm_profiles(self, limit: int = 50, offset: int = 0) -> list[BlueprintLLMProfile]:
        """List all LLM profiles with pagination."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM blueprint_llm_profiles ORDER BY name LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._row_to_llm_profile(r) for r in rows]

    def delete_llm_profile(self, profile_id: str) -> bool:
        """Delete an LLM profile. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM blueprint_llm_profiles WHERE id = ?",
                (profile_id,),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_llm_profile(row: sqlite3.Row) -> BlueprintLLMProfile:
        return BlueprintLLMProfile(
            id=row["id"],
            name=row["name"],
            profile_type=row["profile_type"] if "profile_type" in row.keys() else "text",
            provider=row["provider"],
            model=row["model"],
            api_base=row["api_base"],
            api_key_env=row["api_key_env"],
            max_tokens=row["max_tokens"],
            context_window=row["context_window"],
            temperature=row["temperature"],
            timeout=row["timeout"],
            cost_per_1k_input=row["cost_per_1k_input"],
            cost_per_1k_output=row["cost_per_1k_output"],
            description=row["description"],
            tags=json.loads(row["tags_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            protocol=row["protocol"] if "protocol" in row.keys() else "litellm",
            a2a_endpoint=row["a2a_endpoint"] if "a2a_endpoint" in row.keys() else None,
            a2a_timeout=row["a2a_timeout"] if "a2a_timeout" in row.keys() else 120,
            fallback_llm_profile_id=row["fallback_llm_profile_id"] if "fallback_llm_profile_id" in row.keys() else None,
            a2a_config=json.loads(row["a2a_config_json"]) if "a2a_config_json" in row.keys() and row["a2a_config_json"] else {},
            service_eligible=row["service_eligible"] if "service_eligible" in row.keys() else True,
        )

    # ------------------------------------------------------------------
    # Prompt Templates
    # ------------------------------------------------------------------

    def save_prompt_template(self, template: PromptTemplate) -> None:
        """Insert or replace a prompt template."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO prompt_templates
                    (id, name, role, content, language, variant,
                     description, tags_json, source_path, content_hash,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template.id,
                    template.name,
                    template.role,
                    template.content,
                    template.language,
                    template.variant,
                    template.description,
                    json.dumps(template.tags),
                    template.source_path,
                    template.content_hash,
                    template.created_at.isoformat(),
                    template.updated_at.isoformat(),
                ),
            )
        logger.debug("Saved prompt template %s", template.id)

    def get_prompt_template(self, template_id: str) -> PromptTemplate | None:
        """Retrieve a prompt template by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM prompt_templates WHERE id = ?",
                (template_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_prompt_template(row)

    def list_prompt_templates(
        self,
        role: str | None = None,
        variant: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PromptTemplate]:
        """List prompt templates, optionally filtered by role and/or variant."""
        clauses: list[str] = []
        params: list[str] = []
        if role:
            clauses.append("role = ?")
            params.append(role)
        if variant:
            clauses.append("variant = ?")
            params.append(variant)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM prompt_templates{where} ORDER BY role, name LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
        return [self._row_to_prompt_template(r) for r in rows]

    def delete_prompt_template(self, template_id: str) -> bool:
        """Delete a prompt template. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM prompt_templates WHERE id = ?",
                (template_id,),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_prompt_template(row: sqlite3.Row) -> PromptTemplate:
        return PromptTemplate(
            id=row["id"],
            name=row["name"],
            role=row["role"],
            content=row["content"],
            language=row["language"],
            variant=row["variant"],
            description=row["description"],
            tags=json.loads(row["tags_json"]),
            source_path=row["source_path"],
            content_hash=row["content_hash"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ------------------------------------------------------------------
    # Role Definitions
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Role Types
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Agent Blueprints
    # ------------------------------------------------------------------

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
                    blueprint.prompt_template_id,
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
        tts_voice_id = None
        if "tts_voice_id" in row.keys():
            tts_voice_id = row["tts_voice_id"]
        return AgentBlueprint(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            llm_profile_id=row["llm_profile_id"],
            role_definition_id=row["role_definition_id"],
            prompt_template_id=row["prompt_template_id"],
            tts_voice_id=tts_voice_id,
            tags=json.loads(row["tags_json"]),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ------------------------------------------------------------------
    # Canvas Layouts
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Workflow Definitions
    # ------------------------------------------------------------------

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
                 input_config)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
        )

    # ------------------------------------------------------------------
    # Workflow Templates
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Tone Profiles
    # ------------------------------------------------------------------

    def save_tone_profile(self, profile: ToneProfile) -> None:
        """Insert or replace a tone profile."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tone_profiles
                    (id, name, description, profile_json, is_system,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.id,
                    profile.name,
                    profile.description,
                    profile.model_dump_json(),
                    int(profile.is_system),
                    profile.created_at.isoformat(),
                    profile.updated_at.isoformat(),
                ),
            )
        logger.debug("Saved tone profile %s", profile.id)

    def get_tone_profile(self, profile_id: str) -> ToneProfile | None:
        """Retrieve a tone profile by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tone_profiles WHERE id = ?",
                (profile_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_tone_profile(row)

    def list_tone_profiles(
        self,
        include_system: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ToneProfile]:
        """List tone profiles, optionally filtering system profiles."""
        with self._connect() as conn:
            if include_system:
                rows = conn.execute(
                    "SELECT * FROM tone_profiles ORDER BY is_system DESC, name LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tone_profiles WHERE is_system = 0 ORDER BY name LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        return [self._row_to_tone_profile(r) for r in rows]

    def delete_tone_profile(self, profile_id: str) -> bool:
        """Delete a tone profile. Returns True if a row was deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM tone_profiles WHERE id = ?",
                (profile_id,),
            )
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Argumentation Patterns
    # ------------------------------------------------------------------

    def list_argumentation_patterns(self) -> list[str]:
        """List available argumentation pattern directory names from filesystem."""
        patterns_dir = Path("profiles/argumentation-patterns")
        if not patterns_dir.is_dir():
            return []
        return sorted(d.name for d in patterns_dir.iterdir() if d.is_dir() and not d.name.startswith("."))

    def get_argumentation_pattern(self, name: str) -> dict[str, str] | None:
        """Get all role prompts for a given argumentation pattern.

        Returns a dict mapping role_type_id -> prompt content,
        or None if the pattern directory does not exist.
        """
        pattern_dir = Path(f"profiles/argumentation-patterns/{name}")
        if not pattern_dir.is_dir():
            return None

        result: dict[str, str] = {}
        for md_file in sorted(pattern_dir.glob("*.md")):
            # e.g. "strategist.md" -> role_type_id = "strategist"
            role_type_id = md_file.stem
            # skip language variants like "strategist-en.md"
            if "-" in role_type_id:
                continue
            content = md_file.read_text(encoding="utf-8")
            if content.strip():
                result[role_type_id] = content

        return result if result else None

    # ------------------------------------------------------------------
    # Tone Profiles
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_tone_profile(row: sqlite3.Row) -> ToneProfile:
        """Convert a SQLite row to a ToneProfile model."""
        return ToneProfile.model_validate_json(row["profile_json"])

    # ------------------------------------------------------------------
    # Agent Bundles
    # ------------------------------------------------------------------

    def save_bundle(self, bundle: AgentBundle) -> None:
        """Insert or replace an agent bundle."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_bundles
                    (id, name, description, llm_profile_id, role_type_id,
                     role_definition_id, prompt_template_id, tone_profile_id,
                     persona_id, tags_json, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bundle.id,
                    bundle.name,
                    bundle.description,
                    bundle.llm_profile_id,
                    bundle.role_type_id,
                    bundle.role_definition_id,
                    bundle.prompt_template_id,
                    bundle.tone_profile_id,
                    bundle.persona_id,
                    json.dumps(bundle.tags),
                    int(bundle.is_active),
                    bundle.created_at.isoformat(),
                    bundle.updated_at.isoformat(),
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
        return AgentBundle(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            llm_profile_id=row["llm_profile_id"],
            role_type_id=row["role_type_id"],
            role_definition_id=row["role_definition_id"],
            prompt_template_id=row["prompt_template_id"],
            tone_profile_id=row["tone_profile_id"],
            persona_id=row["persona_id"],
            tags=json.loads(row["tags_json"]),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
