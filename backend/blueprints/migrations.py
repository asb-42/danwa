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
SCHEMA_VERSION = 19


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
        completion_tokens INTEGER NOT NULL DEFAULT 0
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

# ---------------------------------------------------------------------------
# V14 — Seed default role types
# ---------------------------------------------------------------------------

_MIGRATION_V14_SEEDS = [
    """
    INSERT OR IGNORE INTO role_types (id, name, description, icon, color, default_max_rounds, default_consensus_threshold, is_active, created_at, updated_at)
    VALUES ('strategist', 'Strategist', 'Develops strategic approaches and frameworks for analysis', '🧠', '#3b82f6', 5, 0.9, 1, datetime('now'), datetime('now'))
    """,
    """
    INSERT OR IGNORE INTO role_types (id, name, description, icon, color, default_max_rounds, default_consensus_threshold, is_active, created_at, updated_at)
    VALUES ('critic', 'Critic', 'Challenges assumptions and identifies weaknesses in arguments', '🔍', '#ef4444', 5, 0.9, 1, datetime('now'), datetime('now'))
    """,
    """
    INSERT OR IGNORE INTO role_types (id, name, description, icon, color, default_max_rounds, default_consensus_threshold, is_active, created_at, updated_at)
    VALUES ('optimizer', 'Optimizer', 'Refines and improves proposals for efficiency and effectiveness', '⚡', '#f59e0b', 5, 0.9, 1, datetime('now'), datetime('now'))
    """,
    """
    INSERT OR IGNORE INTO role_types (id, name, description, icon, color, default_max_rounds, default_consensus_threshold, is_active, created_at, updated_at)
    VALUES ('moderator', 'Moderator', 'Facilitates discussion and guides the group toward consensus', '🎯', '#10b981', 5, 0.9, 1, datetime('now'), datetime('now'))
    """,
    """
    INSERT OR IGNORE INTO role_types (id, name, description, icon, color, default_max_rounds, default_consensus_threshold, is_active, created_at, updated_at)
    VALUES ('fact-checker', 'Fact Checker', 'Verifies factual claims and cross-references sources', '✅', '#8b5cf6', 5, 0.9, 1, datetime('now'), datetime('now'))
    """,
    """
    INSERT OR IGNORE INTO role_types (id, name, description, icon, color, default_max_rounds, default_consensus_threshold, is_active, created_at, updated_at)
    VALUES ('expert-reviewer', 'Expert Reviewer', 'Provides domain-specific expert assessment and validation', '🎓', '#06b6d4', 5, 0.9, 1, datetime('now'), datetime('now'))
    """,
    """
    INSERT OR IGNORE INTO role_types (id, name, description, icon, color, default_max_rounds, default_consensus_threshold, is_active, created_at, updated_at)
    VALUES ('analyst', 'Analyst', 'Conducts in-depth data analysis and identifies key patterns', '📊', '#06b6d4', 5, 0.9, 1 ,datetime('now'), datetime('now'))
    """,
    """
    INSERT OR IGNORE INTO role_types (id, name, description, icon, color, default_max_rounds, default_consensus_threshold, is_active, created_at, updated_at)
    VALUES ('creative', 'Creative Thinker', 'Generates unconventional ideas and new perspectives', '💡', '#ec4899', 5, 0.9, 1 ,datetime('now'), datetime('now'))
    """,
]


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

        if current < 18:
            logger.info("Applying migration v18: seed analyst, creative, expert-reviewer role types")
            try:
                conn.execute("""
                     INSERT OR IGNORE INTO role_types (id, name, description, icon, color, default_max_rounds, default_consensus_threshold, is_active, created_at, updated_at)
                     VALUES ('analyst', 'Analyst', 'Conducts in-depth data analysis and identifies key patterns', '📊', '#06b6d4', 5, 0.9, 1, 1, datetime('now'), datetime('now'))
                 """)
                conn.execute("""
                     INSERT OR IGNORE INTO role_types (id, name, description, icon, color, default_max_rounds, default_consensus_threshold, is_active, created_at, updated_at)
                     VALUES ('creative', 'Creative Thinker', 'Generates unconventional ideas and new perspectives', '💡', '#ec4899', 5, 0.9, 1, 1, datetime('now'), datetime('now'))
                 """)
                conn.execute("""
                     INSERT OR IGNORE INTO role_types (id, name, description, icon, color, default_max_rounds, default_consensus_threshold, is_active, created_at, updated_at)
                     VALUES ('expert-reviewer', 'Expert Reviewer', 'Provides domain-specific expert assessment and validation', '🎓', '#06b6d4', 5, 0.9, 'functional', 1, datetime('now'), datetime('now'))
                 """)
            except sqlite3.OperationalError as exc:
                logger.debug("V18 seed migration failed: %s", exc)
            _record_version(conn, 18, "Seed analyst, creative, expert-reviewer role types")
            conn.commit()
            logger.info("Migration v18 applied successfully")

        if current < 19:
            logger.info("Applying migration v19: module_registry + module_translation_cache")
            for stmt in _MIGRATION_V19_TABLES:
                conn.execute(stmt)
            _record_version(conn, 19, "Add module_registry + module_translation_cache tables")
            conn.commit()
            logger.info("Migration v19 applied successfully")

        if current >= SCHEMA_VERSION:
            logger.debug("Schema already at version %d — no migrations needed", current)

    finally:
        conn.close()
