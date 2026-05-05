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

from backend.api.deps import get_settings  # noqa: E402
from backend.api.routers import (  # noqa: E402
    audit,
    config,
    debate,
    dms,
    health,
    profiles,
    projects,
    sessions,
    system,
)

# Path to built frontend assets (relative to project root)
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def _setup_logging() -> None:
    """Configure application logging with file + console handlers."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = _LOG_DIR / "debate-agent.log"

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # File handler — detailed, with timestamps
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
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
    app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])
    app.include_router(config.router, prefix="/api/v1/config", tags=["config"])
    app.include_router(dms.router, prefix="/api/v1/dms", tags=["dms"])
    app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
    app.include_router(profiles.router, prefix="/api/v1/profiles", tags=["profiles"])

    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(system.router, prefix="/api/v1/system", tags=["system"])

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
