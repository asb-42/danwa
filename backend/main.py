"""FastAPI application entry point for Danwa Debate Engine.

Version and application metadata are loaded dynamically from
the ``/version`` file via ``settings.app_version``.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env file into os.environ BEFORE any module reads os.getenv()
load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from backend.a2a.router import router as a2a_router  # noqa: E402
from backend.api.deps import get_settings  # noqa: E402
from backend.api.routers import (  # noqa: E402
    a2a_discovery,
    argumentation_patterns,
    assistant,
    audit,
    blueprint_events,
    blueprints,
    bundle_composer,
    canvas,
    config,
    debate,
    debate_stream,
    dms,
    health,
    input_composer,
    llm_profiles,
    modules,
    optimization_proposals,
    output_composer,
    profiles,
    projects,
    role_definitions,
    sessions,
    system,
    tone_profiles,
    workflow_definitions,
    workflow_exec,
    workflow_reports,
    workflow_templates,
)
from backend.api.routers.translation import router as translation_router  # noqa: E402
from backend.api.routers.ui_i18n import router as ui_i18n_router  # noqa: E402
from backend.workflow.hitl.api import router as hitl_router  # noqa: E402

# Path to built frontend assets (relative to project root)
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def _setup_logging() -> None:
    """Configure application logging with file + console handlers.

    The log file is truncated on each application restart to prevent
    unbounded growth.  A ``RotatingFileHandler`` provides an additional
    safety net (10 MB max, 3 backups).
    """
    from logging.handlers import RotatingFileHandler

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = _LOG_DIR / "debate-agent.log"

    # Truncate log file on restart
    try:
        log_file.write_text("", encoding="utf-8")
    except OSError:
        pass  # ignore if file doesn't exist yet

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # File handler — detailed, with timestamps, rotating at 10 MB
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    # Console handler — INFO and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    # Clear existing handlers (uvicorn adds its own) and add ours
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("python_multipart").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("chromadb.utils.embedding_functions").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    _setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Debate Engine starting up...")

    settings = get_settings()
    # Ensure DB directory exists
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)

    # Load settings from YAML file (overrides .env defaults)
    from backend.api.routers.config import _load_settings as _load_yaml_settings

    yaml_settings = _load_yaml_settings()
    if yaml_settings.get("backup"):
        for key, value in yaml_settings["backup"].items():
            if hasattr(settings, key):
                setattr(settings, key, value)
    if yaml_settings.get("ui"):
        ui_lang = yaml_settings["ui"].get("language")
        if ui_lang and hasattr(settings, "ui_language"):
            settings.ui_language = ui_lang
    if yaml_settings.get("utility_llm"):
        svc_llm_id = yaml_settings["utility_llm"].get("service_llm_profile_id")
        if svc_llm_id and hasattr(settings, "service_llm_profile_id"):
            settings.service_llm_profile_id = svc_llm_id

    logger.info("Settings loaded from config/settings.yaml")

    # Run project migration (idempotent)
    from backend.migrations.migrate_projects import migrate_to_projects

    migrate_to_projects()

    # Seed system workflow templates (idempotent)
    from scripts.seed_templates import seed_system_templates

    seed_system_templates()

    # Seed system tone profiles (idempotent)
    from scripts.seed_tone_profiles import seed_system_tone_profiles

    seed_system_tone_profiles()

    # Import modules into DB on startup (idempotent)
    from scripts.deploy_import import main as deploy_import_main

    deploy_import_main()

    yield
    logger.info("Debate Engine shutting down.")

    # --- Shutdown-Backup (Sprint 18) ---
    try:
        from backend.core.config import settings as s

        if s.backup_auto_on_shutdown:
            from backend.persistence.backup import BackupService

            service = BackupService()
            result = service.create_backup(trigger="shutdown")
            logger.info(
                "Shutdown-Backup erstellt: %s (%d Dateien, %d Bytes)",
                result.path,
                result.file_count,
                result.size_bytes,
            )
    except Exception as exc:
        logger.error("Shutdown-Backup fehlgeschlagen: %s", exc)


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routers ---
    app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
    app.include_router(debate.router, prefix="/api/v1/debate", tags=["debate"])
    app.include_router(debate_stream.router, prefix="/api/v1/debate", tags=["debate"])
    app.include_router(hitl_router, prefix="/api/v1/debate", tags=["hitl"])
    app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])
    app.include_router(config.router, prefix="/api/v1/config", tags=["config"])
    app.include_router(dms.router, prefix="/api/v1/dms", tags=["dms"])
    app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
    app.include_router(profiles.router, prefix="/api/v1/profiles", tags=["profiles"])

    # --- Module System ---
    app.include_router(modules.router, prefix="/api/v1/modules", tags=["modules"])

    # --- Translation ---
    app.include_router(translation_router, prefix="/api/v1/translation", tags=["translation"])
    app.include_router(ui_i18n_router, prefix="/api/v1/i18n", tags=["i18n"])

    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(system.router, prefix="/api/v1/system", tags=["system"])

    # --- Blueprint Canvas ---
    app.include_router(blueprints.router, prefix="/api/v1/blueprints", tags=["blueprints"])
    app.include_router(llm_profiles.router, prefix="/api/v1/blueprints/llm-profiles", tags=["blueprints"])
    app.include_router(role_definitions.router, prefix="/api/v1/blueprints", tags=["blueprints"])
    app.include_router(argumentation_patterns.router, prefix="/api/v1/blueprints", tags=["blueprints"])
    app.include_router(workflow_definitions.router, prefix="/api/v1/blueprints/workflows", tags=["blueprints"])
    app.include_router(canvas.router, prefix="/api/v1/canvas", tags=["canvas"])
    app.include_router(
        blueprint_events.router,
        prefix="/api/v1/blueprint-events",
        tags=["blueprint-events"],
    )

    # --- Workflow Execution ---
    app.include_router(
        workflow_exec.router,
        prefix="/api/v1/workflow-exec",
        tags=["workflow-exec"],
    )

    # --- Workflow Reports ---
    app.include_router(
        workflow_reports.router,
        prefix="/api/v1",
        tags=["reports"],
    )

    # --- Workflow Templates ---
    app.include_router(
        workflow_templates.router,
        prefix="/api/v1/workflow-templates",
        tags=["workflow-templates"],
    )

    # --- Bundle Composer ---
    app.include_router(
        bundle_composer.router,
        prefix="/api/v1/bundle-composer",
        tags=["bundle-composer"],
    )

    # --- Tone Profiles ---
    app.include_router(
        tone_profiles.router,
        prefix="/api/v1/tone-profiles",
        tags=["tone-profiles"],
    )

    # --- A2A Discovery ---
    app.include_router(
        a2a_discovery.router,
        prefix="/api/v1/a2a",
        tags=["a2a-discovery"],
    )

    # --- Output Composer ---
    app.include_router(
        output_composer.router,
        prefix="/api/v1",
        tags=["output-composer"],
    )

    # --- Optimization Proposals (Reflection) ---
    app.include_router(
        optimization_proposals.router,
        prefix="/api/v1",
        tags=["optimization-proposals"],
    )

    # --- Input Composer ---
    app.include_router(
        input_composer.router,
        prefix="/api/v1",
        tags=["input-composer"],
    )

    # --- Danwa Assistant ---
    app.include_router(assistant.router)

    # --- Error handlers (Blueprint Canvas) ---
    from backend.api.errors import register_error_handlers

    register_error_handlers(app)

    # --- A2A Protocol (Agent-to-Agent) ---
    # Mounted at root so /.well-known/agent.json discovery works per A2A spec
    app.include_router(a2a_router, tags=["a2a"])

    # --- Static file serving (production mode) ---
    # Mount static assets first (more specific), then SPA fallback last
    if _FRONTEND_DIST.is_dir():
        # Serve built assets (JS, CSS, images)
        app.mount(
            "/assets",
            StaticFiles(directory=_FRONTEND_DIST / "assets"),
            name="static-assets",
        )

        # Serve favicon and other root-level static files
        app.mount(
            "/",
            StaticFiles(directory=_FRONTEND_DIST, html=True),
            name="frontend",
        )

    return app


# Uvicorn entry point
app = create_app()
