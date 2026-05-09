"""FastAPI application entry point for Debate Engine v2.0."""

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
    audit,
    blueprint_events,
    blueprints,
    canvas,
    config,
    debate,
    dms,
    health,
    profiles,
    projects,
    sessions,
    system,
    workflow_exec,
    workflow_reports,
)
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

    # Run project migration (idempotent)
    from backend.migrations.migrate_projects import migrate_to_projects

    migrate_to_projects()

    yield
    logger.info("Debate Engine shutting down.")


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
    app.include_router(hitl_router, prefix="/api/v1/debate", tags=["hitl"])
    app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])
    app.include_router(config.router, prefix="/api/v1/config", tags=["config"])
    app.include_router(dms.router, prefix="/api/v1/dms", tags=["dms"])
    app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
    app.include_router(profiles.router, prefix="/api/v1/profiles", tags=["profiles"])

    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(system.router, prefix="/api/v1/system", tags=["system"])

    # --- Blueprint Canvas ---
    app.include_router(
        blueprints.router, prefix="/api/v1/blueprints", tags=["blueprints"]
    )
    app.include_router(
        canvas.router, prefix="/api/v1/canvas", tags=["canvas"]
    )
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

    # --- A2A Discovery ---
    app.include_router(
        a2a_discovery.router,
        prefix="/api/v1/a2a",
        tags=["a2a-discovery"],
    )

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
