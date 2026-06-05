"""Blueprint Canvas — SQLite schema creation and migrations.

Uses the same pattern as ``backend.services.dms.database.DMSDB`` and
``backend.repositories.profile_repo.ProfileRepository`` — SQLite with
``CREATE TABLE IF NOT EXISTS`` and a ``schema_version`` table for
tracking applied migrations.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/blueprints.db")

# Current schema version — bump when adding new migrations.
SCHEMA_VERSION = 33


def _ensure_schema_version_table(conn: sqlite3.Connection) -> None:
    """Create the schema_version tracking table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            description TEXT NOT NULL DEFAULT '',
            applied_at TEXT NOT NULL
        )
    """)


def _get_current_version(conn: sqlite3.Connection) -> int:
    """Return the highest applied schema version, or 0 if none."""
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return row[0] if row and row[0] is not None else 0


def _record_version(conn: sqlite3.Connection, version: int, description: str = "") -> None:
    """Record that a schema version has been applied."""
    from datetime import UTC, datetime

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, description, applied_at) VALUES (?, ?, ?)",
        (version, description, datetime.now(UTC).isoformat()),
    )


# ---------------------------------------------------------------------------
# Migration SQL statements
# ---------------------------------------------------------------------------

_MIGRATION_V1_TABLES = [
    # --- blueprint_llm_profiles ---
    """
    CREATE TABLE IF NOT EXISTS blueprint_llm_profiles (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        api_base TEXT,
        api_key_env TEXT DEFAULT 'OPENROUTER_API_KEY',
        max_tokens INTEGER DEFAULT 4096,
        context_window INTEGER,
        temperature REAL DEFAULT 0.7,
        timeout INTEGER DEFAULT 600,
        cost_per_1k_input REAL,
        cost_per_1k_output REAL,
        description TEXT DEFAULT '',
        tags_json TEXT DEFAULT '[]',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    # --- prompt_templates ---
    """
    CREATE TABLE IF NOT EXISTS prompt_templates (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        language TEXT DEFAULT 'de',
        variant TEXT DEFAULT 'default',
        description TEXT DEFAULT '',
        tags_json TEXT DEFAULT '[]',
        source_path TEXT,
        content_hash TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_prompt_templates_role ON prompt_templates (role)",
    "CREATE INDEX IF NOT EXISTS idx_prompt_templates_variant ON prompt_templates (variant)",
    # --- role_definitions ---
    """
    CREATE TABLE IF NOT EXISTS role_definitions (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        description TEXT DEFAULT '',
        prompt_template_id TEXT,
        max_rounds INTEGER DEFAULT 5,
        consensus_threshold REAL DEFAULT 0.9,
        tags_json TEXT DEFAULT '[]',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (prompt_template_id) REFERENCES prompt_templates(id) ON DELETE SET NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_role_definitions_role ON role_definitions (role)",
    # --- agent_blueprints ---
    """
    CREATE TABLE IF NOT EXISTS agent_blueprints (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        llm_profile_id TEXT NOT NULL,
        role_definition_id TEXT NOT NULL,
        prompt_template_id TEXT,
        tags_json TEXT DEFAULT '[]',
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (llm_profile_id) REFERENCES blueprint_llm_profiles(id) ON DELETE CASCADE,
        FOREIGN KEY (role_definition_id) REFERENCES role_definitions(id) ON DELETE CASCADE,
        FOREIGN KEY (prompt_template_id) REFERENCES prompt_templates(id) ON DELETE SET NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_agent_blueprints_llm ON agent_blueprints (llm_profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_agent_blueprints_role ON agent_blueprints (role_definition_id)",
    # --- canvas_layouts ---
    """
    CREATE TABLE IF NOT EXISTS canvas_layouts (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        project_id TEXT,
        layout_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_canvas_layouts_project ON canvas_layouts (project_id)",
]


# ---------------------------------------------------------------------------
# Migration v2: workflow_definitions table
# ---------------------------------------------------------------------------

_MIGRATION_V2_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS workflow_definitions (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        canvas_layout_id TEXT,
        execution_order_json TEXT DEFAULT '[]',
        conditional_edges_json TEXT DEFAULT '[]',
        interjection_points_json TEXT DEFAULT '[]',
        node_blueprint_map_json TEXT DEFAULT '{}',
        tags_json TEXT DEFAULT '[]',
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (canvas_layout_id) REFERENCES canvas_layouts(id) ON DELETE SET NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_workflow_def_layout ON workflow_definitions (canvas_layout_id)",
]


# ---------------------------------------------------------------------------
# Migration v3: role_types table
# ---------------------------------------------------------------------------

_MIGRATION_V3_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS role_types (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        icon TEXT DEFAULT '👤',
        color TEXT DEFAULT '#8b5cf6',
        default_max_rounds INTEGER DEFAULT 5,
        default_consensus_threshold REAL DEFAULT 0.9,
        tags_json TEXT DEFAULT '[]',
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
]


# ---------------------------------------------------------------------------
# Migration v4: workflow_definitions graph columns
# ---------------------------------------------------------------------------

_MIGRATION_V4_TABLES = [
    # New columns for structured graph representation
    "ALTER TABLE workflow_definitions ADD COLUMN nodes_json TEXT DEFAULT '[]'",
    "ALTER TABLE workflow_definitions ADD COLUMN edges_json TEXT DEFAULT '[]'",
    "ALTER TABLE workflow_definitions ADD COLUMN entry_point TEXT",
    "ALTER TABLE workflow_definitions ADD COLUMN termination_conditions_json TEXT DEFAULT '[]'",
    "ALTER TABLE workflow_definitions ADD COLUMN version INTEGER DEFAULT 1",
    "ALTER TABLE workflow_definitions ADD COLUMN is_locked INTEGER DEFAULT 0",
]


# ---------------------------------------------------------------------------
# Migration v5: workflow_sessions table
# ---------------------------------------------------------------------------

_MIGRATION_V5_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS workflow_sessions (
        id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL,
        project_id TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        current_node_id TEXT,
        current_round INTEGER DEFAULT 0,
        initial_state_json TEXT,
        result_json TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (workflow_id) REFERENCES workflow_definitions(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_wf_sessions_workflow ON workflow_sessions (workflow_id)",
]


# ---------------------------------------------------------------------------
# Migration v6: audit_log, report_jobs, is_locked/is_archived columns
# ---------------------------------------------------------------------------

_MIGRATION_V6_TABLES = [
    # --- audit_log ---
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        workflow_id TEXT NOT NULL,
        workflow_version INTEGER NOT NULL DEFAULT 1,
        timestamp TEXT NOT NULL,
        event_type TEXT NOT NULL,
        node_id TEXT,
        actor TEXT NOT NULL DEFAULT 'system',
        input_hash TEXT NOT NULL DEFAULT '',
        output_hash TEXT NOT NULL DEFAULT '',
        llm_profile_id TEXT NOT NULL DEFAULT '',
        latency_ms INTEGER NOT NULL DEFAULT 0,
         prompt_tokens INTEGER NOT NULL DEFAULT 0,
         completion_tokens INTEGER NOT NULL DEFAULT 0,
         input_content TEXT NOT NULL DEFAULT '',
         output_content TEXT NOT NULL DEFAULT '',
         trace_log_path TEXT NOT NULL DEFAULT '',
         critic_item_id TEXT NOT NULL DEFAULT '',
         build_response_id TEXT NOT NULL DEFAULT '',
         draft_version INTEGER NOT NULL DEFAULT 0,
         constructivity_score REAL
     )
     """,
    "CREATE INDEX IF NOT EXISTS idx_audit_log_session ON audit_log (session_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_workflow ON audit_log (workflow_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log (event_type)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log (timestamp)",
    # --- report_jobs ---
    """
    CREATE TABLE IF NOT EXISTS report_jobs (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        format TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        file_path TEXT,
        error TEXT,
        created_at TEXT NOT NULL,
        completed_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_report_jobs_session ON report_jobs (session_id)",
    # --- is_locked / is_archived columns on workflow_sessions ---
    "ALTER TABLE workflow_sessions ADD COLUMN is_locked INTEGER DEFAULT 0",
    "ALTER TABLE workflow_sessions ADD COLUMN is_archived INTEGER DEFAULT 0",
    # NOTE: is_locked on state_snapshots is handled in StateSnapshotStore._init_table()
    # because that table is created lazily, not via migrations.
]

# ---------------------------------------------------------------------------
# V7 — A2A Protocol columns on blueprint_llm_profiles (Phase 8)
# ---------------------------------------------------------------------------

_MIGRATION_V7_TABLES = [
    "ALTER TABLE blueprint_llm_profiles ADD COLUMN protocol TEXT DEFAULT 'litellm'",
    "ALTER TABLE blueprint_llm_profiles ADD COLUMN a2a_endpoint TEXT",
    "ALTER TABLE blueprint_llm_profiles ADD COLUMN a2a_timeout INTEGER DEFAULT 120",
    "ALTER TABLE blueprint_llm_profiles ADD COLUMN fallback_llm_profile_id TEXT",
    "ALTER TABLE blueprint_llm_profiles ADD COLUMN a2a_config_json TEXT DEFAULT '{}'",
]

# ---------------------------------------------------------------------------
# V8 — role_type_id on role_definitions (dynamic RoleType reference)
# ---------------------------------------------------------------------------

_MIGRATION_V8_TABLES = [
    # Add role_type_id column (defaults to 'strategist' for backward compat)
    "ALTER TABLE role_definitions ADD COLUMN role_type_id TEXT DEFAULT 'strategist'",
    # Migrate existing 'role' values to role_type_id
    "UPDATE role_definitions SET role_type_id = role WHERE role IS NOT NULL AND role != ''",
    # Set default for role column so NOT NULL constraint is satisfied
    "UPDATE role_definitions SET role = 'strategist' WHERE role IS NULL OR role = ''",
]


# ---------------------------------------------------------------------------
# V9 — workflow_templates table + template_id on workflow_definitions
# ---------------------------------------------------------------------------

_MIGRATION_V9_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS workflow_templates (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        category TEXT NOT NULL DEFAULT 'custom',
        tags_json TEXT DEFAULT '[]',
        template_data_json TEXT NOT NULL DEFAULT '{}',
        placeholders_json TEXT NOT NULL DEFAULT '[]',
        is_system INTEGER DEFAULT 0,
        source_workflow_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_wf_templates_category ON workflow_templates (category)",
    "CREATE INDEX IF NOT EXISTS idx_wf_templates_is_system ON workflow_templates (is_system)",
    # Add template_id column to workflow_definitions (for tracking template origin)
    "ALTER TABLE workflow_definitions ADD COLUMN template_id TEXT",
]

_MIGRATION_V10_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS tone_profiles (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        profile_json TEXT NOT NULL DEFAULT '{}',
        is_system INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tone_profiles_is_system ON tone_profiles (is_system)",
]

# ---------------------------------------------------------------------------
# V11 — Output Composer tables: debate_artifacts, render_jobs, tts_voices,
#        optimization_proposals
# ---------------------------------------------------------------------------

_MIGRATION_V11_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS debate_artifacts (
        session_id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL,
        data TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_debate_artifacts_workflow ON debate_artifacts (workflow_id)",
    """
    CREATE TABLE IF NOT EXISTS render_jobs (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        plugin_key TEXT NOT NULL,
        config TEXT DEFAULT '{}',
        status TEXT DEFAULT 'queued',
        output_files TEXT DEFAULT '[]',
        error_message TEXT,
        artifact_snapshot_hash TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_render_jobs_session ON render_jobs (session_id)",
    "CREATE INDEX IF NOT EXISTS idx_render_jobs_status ON render_jobs (status)",
    """
    CREATE TABLE IF NOT EXISTS tts_voices (
        voice_id TEXT PRIMARY KEY,
        name TEXT,
        language TEXT,
        gender TEXT,
        provider TEXT DEFAULT 'edge_tts',
        is_active INTEGER DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tts_voices_language ON tts_voices (language)",
    """
    CREATE TABLE IF NOT EXISTS optimization_proposals (
        id TEXT PRIMARY KEY,
        target_workflow_id TEXT NOT NULL,
        source_session_id TEXT,
        proposed_nodes_json TEXT DEFAULT '[]',
        proposed_edges_json TEXT DEFAULT '[]',
        rationale TEXT DEFAULT '',
        risk_assessment TEXT DEFAULT '',
        estimated_impact TEXT DEFAULT '',
        status TEXT DEFAULT 'pending',
        created_by TEXT DEFAULT 'meta_agent',
        approved_by TEXT,
        approved_at TEXT,
        parent_version_id TEXT DEFAULT '',
        new_version_id TEXT,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_opt_proposals_workflow ON optimization_proposals (target_workflow_id)",
    "CREATE INDEX IF NOT EXISTS idx_opt_proposals_status ON optimization_proposals (status)",
]

# ---------------------------------------------------------------------------
# V12 — Input Composer tables: input_jobs, a2a_inbound_tasks,
#        debate_inputs; extend blueprint_llm_profiles + workflow_definitions
# ---------------------------------------------------------------------------

_MIGRATION_V12_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS input_jobs (
        id TEXT PRIMARY KEY,
        plugin_key TEXT NOT NULL,
        config TEXT DEFAULT '{}',
        raw_input_data TEXT DEFAULT '{}',
        processed_input TEXT,
        status TEXT DEFAULT 'queued',
        error_message TEXT,
        created_at TEXT NOT NULL,
        completed_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_input_jobs_status ON input_jobs (status)",
    "CREATE INDEX IF NOT EXISTS idx_input_jobs_plugin ON input_jobs (plugin_key)",
    """
    CREATE TABLE IF NOT EXISTS a2a_inbound_tasks (
        task_id TEXT PRIMARY KEY,
        agent_id TEXT,
        message_preview TEXT,
        input_job_id TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_a2a_inbound_status ON a2a_inbound_tasks (status)",
    """
    CREATE TABLE IF NOT EXISTS debate_inputs (
        session_id TEXT PRIMARY KEY,
        data TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
]
# NOTE: ALTER TABLE workflow_definitions ADD COLUMN input_config is handled
# separately in run_migrations() with try/except since SQLite doesn't support
# IF NOT EXISTS for column additions.

# ---------------------------------------------------------------------------
# V13 — profile_type column on blueprint_llm_profiles
# ---------------------------------------------------------------------------

_MIGRATION_V13_TABLES = [
    "ALTER TABLE blueprint_llm_profiles ADD COLUMN profile_type TEXT DEFAULT 'text'",
    "CREATE INDEX IF NOT EXISTS idx_llm_profiles_type ON blueprint_llm_profiles (profile_type)",
]

# V14 — Seed default role types (seeds removed in V33; tables dropped)
_MIGRATION_V14_SEEDS: list[str] = []


# ---------------------------------------------------------------------------
# Migration v15: tts_voice_id on agent_blueprints
# ---------------------------------------------------------------------------

_MIGRATION_V15_TABLES = [
    """
    ALTER TABLE agent_blueprints ADD COLUMN tts_voice_id TEXT DEFAULT NULL
    """,
]


# ---------------------------------------------------------------------------
# V19 - Module Registry: module_registry + module_translation_cache
# ---------------------------------------------------------------------------

_MIGRATION_V19_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS module_registry (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        type TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'custom',
        version TEXT NOT NULL DEFAULT '0.0.0',
        author_json TEXT DEFAULT '{}',
        license TEXT DEFAULT 'CC-BY-4.0',
        checksum TEXT,
        installed_at TEXT NOT NULL,
        updated_at TEXT,
        enabled INTEGER DEFAULT 1,
        source_url TEXT,
        source_schema TEXT DEFAULT '1.0.0',
        tags_json TEXT DEFAULT '[]'
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_module_registry_type ON module_registry (type);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_module_registry_category ON module_registry (category);
    """,
    """
    CREATE TABLE IF NOT EXISTS module_translation_cache (
        id TEXT PRIMARY KEY,
        module_id TEXT NOT NULL,
        file_path TEXT NOT NULL,
        language TEXT NOT NULL DEFAULT 'en',
        translated_content TEXT,
        source_hash TEXT,
        quality_score REAL DEFAULT 0.0,
        generated_at TEXT,
        generated_by TEXT,
        approved INTEGER DEFAULT 0,
        FOREIGN KEY (module_id) REFERENCES module_registry(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_module_trans ON module_translation_cache (module_id, language);
    """,
]


# ---------------------------------------------------------------------------
# V20 — Module Registry: dependencies column
# ---------------------------------------------------------------------------

_MIGRATION_V20_TABLES = [
    "ALTER TABLE module_registry ADD COLUMN dependencies TEXT DEFAULT '{}'",
]


# ---------------------------------------------------------------------------
# V21 — Translation cache: source_language + source_content columns
# ---------------------------------------------------------------------------

_MIGRATION_V21_TABLES = [
    "ALTER TABLE module_translation_cache ADD COLUMN source_language TEXT DEFAULT 'en'",
    "ALTER TABLE module_translation_cache ADD COLUMN source_content TEXT DEFAULT ''",
    "ALTER TABLE module_translation_cache ADD COLUMN back_translation TEXT",
    "ALTER TABLE module_translation_cache ADD COLUMN generated_by TEXT DEFAULT 'system'",
    "ALTER TABLE module_translation_cache ADD COLUMN error TEXT",
]


# ---------------------------------------------------------------------------
# V22 — Audit log content columns (no-op: already in v6 CREATE TABLE)
# ---------------------------------------------------------------------------

_MIGRATION_V22_TABLES: list[str] = []


# ---------------------------------------------------------------------------
# V23 — Trace log path (no-op: already in v6 CREATE TABLE)
# ---------------------------------------------------------------------------

_MIGRATION_V23_TABLES: list[str] = []


# ---------------------------------------------------------------------------
# V24 — Module translation cache: UNIQUE constraint for ON CONFLICT support
# ---------------------------------------------------------------------------

_MIGRATION_V24_TABLES = [
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_module_trans_cache_uniq ON module_translation_cache (module_id, file_path, language)",
]
# ---------------------------------------------------------------------------
# V25 — service_eligible column on blueprint_llm_profiles
# ---------------------------------------------------------------------------

_MIGRATION_V25_TABLES = [
    "ALTER TABLE blueprint_llm_profiles ADD COLUMN service_eligible INTEGER DEFAULT 1",
]

# ---------------------------------------------------------------------------
# V26 — agent_bundles table (Bundle architecture)
# ---------------------------------------------------------------------------

_MIGRATION_V26_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS agent_bundles (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        llm_profile_id TEXT NOT NULL,
        role_type_id TEXT NOT NULL,
        role_definition_id TEXT,
        prompt_template_id TEXT,
        tone_profile_id TEXT,
        persona_id TEXT,
        tags_json TEXT DEFAULT '[]',
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (llm_profile_id) REFERENCES blueprint_llm_profiles(id) ON DELETE CASCADE,
        FOREIGN KEY (role_type_id) REFERENCES role_types(id) ON DELETE CASCADE,
        FOREIGN KEY (role_definition_id) REFERENCES role_definitions(id) ON DELETE SET NULL,
        FOREIGN KEY (prompt_template_id) REFERENCES prompt_templates(id) ON DELETE SET NULL,
        FOREIGN KEY (tone_profile_id) REFERENCES tone_profiles(id) ON DELETE SET NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_agent_bundles_llm ON agent_bundles (llm_profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_agent_bundles_role_type ON agent_bundles (role_type_id)",
    "CREATE INDEX IF NOT EXISTS idx_agent_bundles_active ON agent_bundles (is_active)",
]

_MIGRATION_V27_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS prompt_modifiers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        content TEXT NOT NULL,
        description TEXT DEFAULT '',
        tags_json TEXT DEFAULT '[]',
        is_system INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
]


def run_migrations(db_path: Path | str = _DEFAULT_DB_PATH) -> None:
    """Apply all pending schema migrations.

    Safe to call multiple times — only unapplied migrations are executed.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        _ensure_schema_version_table(conn)
        current = _get_current_version(conn)

        if current < 1:
            logger.info("Applying migration v1: blueprint tables")
            for stmt in _MIGRATION_V1_TABLES:
                conn.execute(stmt)
            _record_version(conn, 1, "Initial blueprint schema")
            conn.commit()
            logger.info("Migration v1 applied successfully")

        if current < 2:
            logger.info("Applying migration v2: workflow_definitions table")
            for stmt in _MIGRATION_V2_TABLES:
                conn.execute(stmt)
            _record_version(conn, 2, "Add workflow_definitions table")
            conn.commit()
            logger.info("Migration v2 applied successfully")

        if current < 3:
            logger.info("Applying migration v3: role_types table")
            for stmt in _MIGRATION_V3_TABLES:
                conn.execute(stmt)
            _record_version(conn, 3, "Add role_types table")
            conn.commit()
            logger.info("Migration v3 applied successfully")

        if current < 4:
            logger.info("Applying migration v4: workflow graph columns")
            for stmt in _MIGRATION_V4_TABLES:
                conn.execute(stmt)
            _record_version(
                conn,
                4,
                "Add workflow graph columns (nodes, edges, entry_point, termination, version, is_locked)",
            )
            conn.commit()
            logger.info("Migration v4 applied successfully")

        if current < 5:
            logger.info("Applying migration v5: workflow_sessions table")
            for stmt in _MIGRATION_V5_TABLES:
                conn.execute(stmt)
            _record_version(conn, 5, "Add workflow_sessions table")
            conn.commit()
            logger.info("Migration v5 applied successfully")

        if current < 6:
            logger.info("Applying migration v6: audit_log, report_jobs, immutability columns")
            for stmt in _MIGRATION_V6_TABLES:
                conn.execute(stmt)
            _record_version(conn, 6, "Add audit_log, report_jobs tables; is_locked/is_archived columns")
            conn.commit()
            logger.info("Migration v6 applied successfully")

        if current < 7:
            logger.info("Applying migration v7: A2A protocol columns on blueprint_llm_profiles")
            for stmt in _MIGRATION_V7_TABLES:
                conn.execute(stmt)
            _record_version(conn, 7, "Add A2A protocol columns to blueprint_llm_profiles")
            conn.commit()
            logger.info("Migration v7 applied successfully")

        if current < 8:
            logger.info("Applying migration v8: role_type_id on role_definitions")
            for stmt in _MIGRATION_V8_TABLES:
                conn.execute(stmt)
            _record_version(conn, 8, "Add role_type_id to role_definitions")
            conn.commit()
            logger.info("Migration v8 applied successfully")

        if current < 9:
            logger.info("Applying migration v9: workflow_templates table")
            for stmt in _MIGRATION_V9_TABLES:
                conn.execute(stmt)
            _record_version(conn, 9, "Add workflow_templates table and template_id on workflow_definitions")
            conn.commit()
            logger.info("Migration v9 applied successfully")

        if current < 10:
            logger.info("Applying migration v10: tone_profiles table")
            for stmt in _MIGRATION_V10_TABLES:
                conn.execute(stmt)
            _record_version(conn, 10, "Add tone_profiles table")
            conn.commit()
            logger.info("Migration v10 applied successfully")

        if current < 11:
            logger.info("Applying migration v11: output composer tables")
            for stmt in _MIGRATION_V11_TABLES:
                conn.execute(stmt)
            _record_version(conn, 11, "Add debate_artifacts, render_jobs, tts_voices, optimization_proposals")
            conn.commit()
            logger.info("Migration v11 applied successfully")

        if current < 12:
            logger.info("Applying migration v12: input composer tables")
            for stmt in _MIGRATION_V12_TABLES:
                conn.execute(stmt)
            # ALTER TABLE for workflow_definitions.input_config
            # (handled separately since SQLite doesn't support IF NOT EXISTS)
            try:
                conn.execute("ALTER TABLE workflow_definitions ADD COLUMN input_config TEXT DEFAULT NULL")
            except sqlite3.OperationalError:
                logger.debug("workflow_definitions.input_config column already exists")
            _record_version(
                conn,
                12,
                "Add input_jobs, a2a_inbound_tasks, stt_voices, debate_inputs; extend workflow_definitions",
            )
            conn.commit()
            logger.info("Migration v12 applied successfully")

        if current < 13:
            logger.info("Applying migration v13: profile_type on blueprint_llm_profiles")
            for stmt in _MIGRATION_V13_TABLES:
                conn.execute(stmt)
            _record_version(conn, 13, "Add profile_type column to blueprint_llm_profiles")
            conn.commit()
            logger.info("Migration v13 applied successfully")

        if current < 14:
            logger.info("Applying migration v14: seed default role types")
            for stmt in _MIGRATION_V14_SEEDS:
                conn.execute(stmt)
            _record_version(
                conn,
                14,
                "Seed default role types (strategist, critic, optimizer, moderator, fact-checker, expert-reviewer, analyst, creative)",
            )
            conn.commit()
            logger.info("Migration v14 applied successfully")

        if current < 15:
            logger.info("Applying migration v15: tts_voice_id on agent_blueprints")
            for stmt in _MIGRATION_V15_TABLES:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    logger.debug("tts_voice_id column already exists on agent_blueprints")
            _record_version(conn, 15, "Add tts_voice_id to agent_blueprints")
            conn.commit()
            logger.info("Migration v15 applied successfully")

        if current < 16:
            logger.info("Applying migration v16: fix profile_type from model/name heuristics")
            try:
                conn.execute("""
                    UPDATE blueprint_llm_profiles
                    SET profile_type = 'tts'
                    WHERE profile_type = 'text'
                      AND (LOWER(model) LIKE '%tts%' OR LOWER(name) LIKE '%tts%')
                """)
                conn.execute("""
                    UPDATE blueprint_llm_profiles
                    SET profile_type = 'stt'
                    WHERE profile_type = 'text'
                      AND (LOWER(model) LIKE '%stt%' OR LOWER(model) LIKE '%whisper%'
                           OR LOWER(name) LIKE '%stt%' OR LOWER(name) LIKE '%whisper%')
                """)
            except sqlite3.OperationalError as exc:
                logger.debug("Migration v16 heuristic update failed: %s", exc)
            _record_version(conn, 16, "Fix profile_type heuristics for existing TTS/STT profiles")
            conn.commit()
            logger.info("Migration v16 applied successfully")

        if current < 17:
            logger.info("Applying migration v17: category on role_types, argumentation_pattern+mode on role_definitions")
            try:
                conn.execute("ALTER TABLE role_types ADD COLUMN category TEXT DEFAULT 'functional'")
            except sqlite3.OperationalError:
                logger.debug("role_types.category column already exists")
            try:
                conn.execute("ALTER TABLE role_definitions ADD COLUMN argumentation_pattern TEXT")
            except sqlite3.OperationalError:
                logger.debug("role_definitions.argumentation_pattern column already exists")
            try:
                conn.execute("ALTER TABLE role_definitions ADD COLUMN mode TEXT")
            except sqlite3.OperationalError:
                logger.debug("role_definitions.mode column already exists")
            _record_version(conn, 17, "Add category to role_types, argumentation_pattern+mode to role_definitions")
            conn.commit()
            logger.info("Migration v17 applied successfully")

        # V18 — role_types seeds removed (table dropped in V33)
        if current < 18:
            _record_version(conn, 18, "Seed analyst, creative, expert-reviewer role types (removed in V33)")
            conn.commit()

        if current < 19:
            logger.info("Applying migration v19: module_registry + module_translation_cache")
            for stmt in _MIGRATION_V19_TABLES:
                conn.execute(stmt)
            _record_version(conn, 19, "Add module_registry + module_translation_cache tables")
            conn.commit()
            logger.info("Migration v19 applied successfully")

        if current < 20:
            logger.info("Applying migration v20: dependencies column on module_registry")
            for stmt in _MIGRATION_V20_TABLES:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    logger.debug("dependencies column already exists on module_registry")
            _record_version(conn, 20, "Add dependencies column to module_registry")
            conn.commit()
            logger.info("Migration v20 applied successfully")

        if current < 21:
            logger.info("Applying migration v21: source_language + source_content on module_translation_cache")
            for stmt in _MIGRATION_V21_TABLES:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    logger.debug("source_language/source_content column already exists on module_translation_cache")
            _record_version(
                conn, 21, "Add source_language + source_content + back_translation + generated_by + error columns to module_translation_cache"
            )
            conn.commit()
            logger.info("Migration v21 applied successfully")

        # ── V22 — Audit log content columns ──
        if current < 22:
            logger.info("Applying migration v22: input_content + output_content on audit_log")
            try:
                for stmt in _MIGRATION_V22_TABLES:
                    conn.execute(stmt)
                _record_version(conn, 22, "Add input_content + output_content columns to audit_log")
                conn.commit()
                logger.info("Migration v22 applied successfully")
            except sqlite3.OperationalError as exc:
                logger.debug("Migration v22 skipped: %s", exc)

        # ── V23 — Trace log path ──
        if current < 23:
            logger.info("Applying migration v23: trace_log_path on audit_log")
            try:
                for stmt in _MIGRATION_V23_TABLES:
                    conn.execute(stmt)
                _record_version(conn, 23, "Add trace_log_path column to audit_log")
                conn.commit()
                logger.info("Migration v23 applied successfully")
            except sqlite3.OperationalError as exc:
                logger.debug("Migration v23 skipped: %s", exc)

        # ── V24 — UNIQUE constraint on module_translation_cache ──
        if current < 24:
            logger.info("Applying migration v24: UNIQUE constraint on module_translation_cache")
            try:
                for stmt in _MIGRATION_V24_TABLES:
                    conn.execute(stmt)
                _record_version(conn, 24, "Add UNIQUE index on module_translation_cache (module_id, file_path, language)")
                conn.commit()
                logger.info("Migration v24 applied successfully")
            except sqlite3.OperationalError as exc:
                logger.debug("Migration v24 skipped: %s", exc)

        # ── V25 — service_eligible column ──
        if current < 25:
            logger.info("Applying migration v25: service_eligible column on blueprint_llm_profiles")
            try:
                for stmt in _MIGRATION_V25_TABLES:
                    conn.execute(stmt)
                _record_version(conn, 25, "Add service_eligible column to blueprint_llm_profiles")
                conn.commit()
                logger.info("Migration v25 applied successfully")
            except sqlite3.OperationalError as exc:
                logger.debug("Migration v25 skipped: %s", exc)

        # ── V26 — agent_bundles table ──
        if current < 26:
            logger.info("Applying migration v26: agent_bundles table")
            for stmt in _MIGRATION_V26_TABLES:
                conn.execute(stmt)
            _record_version(conn, 26, "Add agent_bundles table for Bundle architecture")
            conn.commit()
            logger.info("Migration v26 applied successfully")

        # ── V27 — prompt_modifiers table + composition_json on agent_bundles ──
        if current < 27:
            logger.info("Applying migration v27: prompt_modifiers table + composition_json on agent_bundles")
            for stmt in _MIGRATION_V27_TABLES:
                conn.execute(stmt)
            try:
                conn.execute("ALTER TABLE agent_bundles ADD COLUMN composition_json TEXT")
            except sqlite3.OperationalError:
                logger.debug("agent_bundles.composition_json column already exists")
            _record_version(conn, 27, "Add prompt_modifiers table + composition_json column to agent_bundles")
            conn.commit()
            logger.info("Migration v27 applied successfully")

        # ── V28 — phase_configs_json on workflow_definitions ──
        if current < 28:
            logger.info("Applying migration v28: phase_configs_json column on workflow_definitions")
            try:
                conn.execute("ALTER TABLE workflow_definitions ADD COLUMN phase_configs_json TEXT DEFAULT '{}'")
                _record_version(conn, 28, "Add phase_configs_json column to workflow_definitions for multi-phase debate support")
                conn.commit()
                logger.info("Migration v28 applied successfully")
            except sqlite3.OperationalError as exc:
                logger.debug("Migration v28 skipped: %s", exc)

        # ── V29 — model_params_json on agent_bundles ──
        if current < 29:
            logger.info("Applying migration v29: model_params_json column on agent_bundles")
            try:
                conn.execute("ALTER TABLE agent_bundles ADD COLUMN model_params_json TEXT DEFAULT '{}'")
                _record_version(conn, 29, "Add model_params_json column to agent_bundles for per-bundle LLM inference overrides")
                conn.commit()
                logger.info("Migration v29 applied successfully")
            except sqlite3.OperationalError as exc:
                logger.debug("Migration v29 skipped: %s", exc)

        # ── V30 — progress columns on render_jobs ──
        if current < 30:
            logger.info("Applying migration v30: progress columns on render_jobs")
            try:
                conn.execute("ALTER TABLE render_jobs ADD COLUMN progress_current INTEGER DEFAULT 0")
            except sqlite3.OperationalError as exc:
                logger.debug("render_jobs.progress_current column already exists: %s", exc)
            try:
                conn.execute("ALTER TABLE render_jobs ADD COLUMN progress_total INTEGER DEFAULT 0")
            except sqlite3.OperationalError as exc:
                logger.debug("render_jobs.progress_total column already exists: %s", exc)
            _record_version(conn, 30, "Add progress_current and progress_total columns to render_jobs for real-time progress tracking")
            conn.commit()
            logger.info("Migration v30 applied successfully")

        # ── V31 — structured audit columns for transactional drafting ──
        if current < 31:
            logger.info("Applying migration v31: structured audit columns for transactional drafting")
            try:
                conn.execute("ALTER TABLE audit_log ADD COLUMN critic_item_id TEXT")
            except sqlite3.OperationalError as exc:
                logger.debug("audit_log.critic_item_id already exists: %s", exc)
            try:
                conn.execute("ALTER TABLE audit_log ADD COLUMN build_response_id TEXT")
            except sqlite3.OperationalError as exc:
                logger.debug("audit_log.build_response_id already exists: %s", exc)
            try:
                conn.execute("ALTER TABLE audit_log ADD COLUMN draft_version INTEGER DEFAULT 0")
            except sqlite3.OperationalError as exc:
                logger.debug("audit_log.draft_version already exists: %s", exc)
            try:
                conn.execute("ALTER TABLE audit_log ADD COLUMN constructivity_score REAL")
            except sqlite3.OperationalError as exc:
                logger.debug("audit_log.constructivity_score already exists: %s", exc)
            _record_version(conn, 31, "Add critic_item_id, build_response_id, draft_version, constructivity_score to audit_log")
            conn.commit()
            logger.info("Migration v31 applied successfully")

        # ── V32 — build_response_provenance table for clause lineage ──
        if current < 32:
            logger.info("Applying migration v32: create build_response_provenance table")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS build_response_provenance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    workflow_id TEXT NOT NULL,
                    response_to TEXT NOT NULL,
                    draft_version INTEGER DEFAULT 0,
                    critic_item_id TEXT DEFAULT '',
                    original_text TEXT DEFAULT '',
                    revision_type TEXT DEFAULT 'conservative',
                    pragmatist_verdict TEXT,
                    pragmatist_score REAL,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_provenance_session ON build_response_provenance(session_id)")
            _record_version(conn, 32, "Create build_response_provenance table for clause lineage tracking")
            conn.commit()
            logger.info("Migration v32 applied successfully")

        # ── V33 — Drop legacy role_types, role_definitions, prompt_templates tables ──
        if current < 33:
            logger.info("Applying migration v33: drop legacy role_types, role_definitions, prompt_templates")

            # SQLite doesn't support ALTER TABLE … DROP CONSTRAINT.
            # Recreate agent_blueprints and agent_bundles without the FK
            # constraints that reference the three legacy tables, then drop
            # the legacy tables.
            conn.execute("PRAGMA foreign_keys=OFF")

            # ── Recreate agent_blueprints (keep llm_profile_id FK only) ──
            conn.execute("ALTER TABLE agent_blueprints RENAME TO _ab_old")
            conn.execute("""
                CREATE TABLE agent_blueprints (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    llm_profile_id TEXT NOT NULL,
                    role_definition_id TEXT NOT NULL,
                    prompt_template_id TEXT,
                    tags_json TEXT DEFAULT '[]',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    tts_voice_id TEXT DEFAULT NULL,
                    FOREIGN KEY (llm_profile_id)
                        REFERENCES blueprint_llm_profiles(id) ON DELETE CASCADE
                )
            """)
            conn.execute(
                "INSERT INTO agent_blueprints "
                "SELECT id, name, description, llm_profile_id, role_definition_id, "
                "       prompt_template_id, tags_json, is_active, created_at, updated_at, "
                "       tts_voice_id "
                "FROM _ab_old"
            )
            conn.execute("DROP TABLE _ab_old")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_blueprints_llm ON agent_blueprints (llm_profile_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_blueprints_role ON agent_blueprints (role_definition_id)")

            # ── Recreate agent_bundles (keep llm_profile_id + tone_profile_id FKs) ──
            conn.execute("ALTER TABLE agent_bundles RENAME TO _bun_old")
            conn.execute("""
                CREATE TABLE agent_bundles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    llm_profile_id TEXT NOT NULL,
                    role_type_id TEXT NOT NULL,
                    role_definition_id TEXT,
                    prompt_template_id TEXT,
                    tone_profile_id TEXT,
                    persona_id TEXT,
                    tags_json TEXT DEFAULT '[]',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    composition_json TEXT,
                    model_params_json TEXT DEFAULT '{}',
                    FOREIGN KEY (llm_profile_id)
                        REFERENCES blueprint_llm_profiles(id) ON DELETE CASCADE,
                    FOREIGN KEY (tone_profile_id)
                        REFERENCES tone_profiles(id) ON DELETE SET NULL
                )
            """)
            conn.execute(
                "INSERT INTO agent_bundles "
                "SELECT id, name, description, llm_profile_id, role_type_id, "
                "       role_definition_id, prompt_template_id, tone_profile_id, persona_id, "
                "       tags_json, is_active, created_at, updated_at, "
                "       composition_json, model_params_json "
                "FROM _bun_old"
            )
            conn.execute("DROP TABLE _bun_old")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_bundles_llm ON agent_bundles (llm_profile_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_bundles_role_type ON agent_bundles (role_type_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_bundles_active ON agent_bundles (is_active)")

            # ── Drop legacy tables ──
            conn.execute("DROP TABLE IF EXISTS prompt_templates")
            conn.execute("DROP TABLE IF EXISTS role_definitions")
            conn.execute("DROP TABLE IF EXISTS role_types")

            conn.execute("PRAGMA foreign_keys=ON")
            _record_version(
                conn,
                33,
                "Drop legacy role_types, role_definitions, prompt_templates; remove FK constraints from agent_blueprints and agent_bundles",
            )
            conn.commit()
            logger.info("Migration v33 applied successfully")

        if current >= SCHEMA_VERSION:
            logger.debug("Schema already at version %d — no migrations needed", current)

    finally:
        conn.close()
